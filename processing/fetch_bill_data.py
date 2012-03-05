#!/usr/bin/python
'''
Code for accumulating Skyline-generated energy into "shadow" registers in
meters of reebills.
'''
import sys
import os  
from pprint import pprint, pformat
from types import NoneType
from datetime import date, datetime,timedelta, time
import calendar
import random
import csv
from bisect import bisect_left
from optparse import OptionParser
from skyliner import sky_install
from skyliner import sky_objects
from skyliner.sky_errors import DataHandlerError
from billing import mongo
from billing.dictutils import dict_merge
from billing import dateutils

def fetch_oltp_data(splinter, olap_id, reebill):
    '''Update quantities of shadow registers in reebill with Skyline-generated
    energy from OLTP.'''
    inst_obj = splinter.get_install_obj_for(olap_id)
    energy_function = lambda day, hourrange: inst_obj.get_billable_energy(day,
            hourrange, places=5)
    usage_data_to_virtual_register(reebill, energy_function)

def fetch_interval_meter_data(reebill, csv_file):
    '''Update quantities of shadow registers in reebill with interval-meter
    energy values from csv_file.'''
    energy_function = get_interval_meter_data_source(csv_file)
    usage_data_to_virtual_register(reebill, energy_function)
    

def get_interval_meter_data_source(csv_file):
    '''Returns a function mapping hours (as datetimes) to hourly energy
    measurements from an interval meter. These measurements should come as a
    CSV file with ISO 8601 timestamps in the first column, energy in the second
    column, and energy units in the third, e.g.:
            2012-01-01T03:45:00Z, 1.234, therms

    Timestamps must be at :00, :15, :30, :45, and the energy value associated
    with each timestamp is assumed to cover the quarter hour preceding that
    timestamp.

    We can't compute the energy offset provided by the difference between
    two measurements when there are time-of-use registers, because it depends
    what the utility would have measured at a particular time, and we have no
    way to know that--so instead we put the full amount of energy measured by
    the interval meter into the shadow registers. This energy is not an offset,
    so we're using the shadow registers in a completely different way from how
    they were intended to be used. But the meaning of shadow registers will
    change: instead of using real and shadow registers to compute actual and
    hypothetical charges as we do for Skyline bills, we will treat them just as
    pairs of energy measurements whose meaning can change depending on how
    they're used. '''

    # read data in format [(timestamp, value)]
    timestamps = []
    values  = []

    # auto-detect csv format variation by reading the file, then reset file
    # pointer to beginning
    csv_dialect = csv.Sniffer().sniff(csv_file.read(1024))
    csv_file.seek(0)

    reader = csv.reader(csv_file, dialect=csv_dialect)
    for row in reader:
        timestamp_str, value, unit = row
        timestamp = datetime.strptime(timestamp_str, dateutils.ISO_8601_DATETIME)
        if unit == 'therms':
            value = value
        else:
            raise Exception('unknown unit: ' + unit)
        timestamps.append(timestamp)
        values.append(float(value))
    if len(timestamps) < 4:
        raise Exception('CSV file has only %s rows, but needs at least 4' \
                % len(timestamps))

    # function that will return energy for an hour range ((start, end) pair,
    # inclusive)
    def get_energy_for_hour_range(day, hour_range):
        # first timestamp is at :15; last is at :00
        first_timestamp = datetime(day.year, day.month, day.day, hour_range[0], 15)
        last_timestamp = datetime(day.year, day.month, day.day, hour_range[1]) \
                + timedelta(hours=1)

        # validate hour range
        if first_timestamp < timestamps[0]:
            # TODO clarify these error messages
            raise IndexError(('First timestamp for %s %s is %s, which precedes'
                ' earliest timestamp in CSV file: %s') % (day, hour_range,
                first_timestamp, timestamps[0]))
        elif last_timestamp > timestamps[-1]:
            raise IndexError(('Last timestamp for %s %s is %s, which follows'
                ' latest timestamp in CSV file: %s') % (day, hour_range,
                last_timestamp, timestamps[-1]))
        
        # binary search the timestamps list to find the first one >=
        # first_timestamp
        first_timestamp_index = bisect_left(timestamps, first_timestamp)

        # iterate over the hour range, adding up energy at 15-mintute intervals
        # and also checking timestamps
        total = 0
        i = first_timestamp_index
        while timestamps[i] <= last_timestamp:
            print >> sys.stderr, 'getting energy for %s' % timestamps[i]
            expected_timestamp = first_timestamp + timedelta(
                    hours=.25*(i - first_timestamp_index))
            if timestamps[i] != expected_timestamp:
                raise Exception(('Bad timestamps for hour range %s %s: '
                    'expected %s, found %s') % (day, hour_range,
                        expected_timestamp, timestamps[i]))
            total += values[i]
            i+= 1
        return total

    return get_energy_for_hour_range


def get_shadow_register_data(reebill):
    '''Returns a list of shadow registers in all meters of the given
    MongoReebill. The returned dictionaries are the same as register
    subdocuments in mongo plus read dates of their containing meters.'''
    result = []
    service_meters_dict = reebill.meters # poorly-named attribute
    for service, meters in service_meters_dict.iteritems():
        for meter in meters:
            for register in meter['registers']:
                if register['shadow'] == True:
                    result.append(dict_merge(register.copy(), {
                        'prior_read_date': meter['prior_read_date'],
                        'present_read_date': meter['present_read_date']
                    }))
    return result

def usage_data_to_virtual_register(reebill, energy_function):
    '''Gets energy quantities from 'energy_function' and puts them in the total
    fields of the appropriate shadow registers in the MongoReebill object
    reebill. 'energy_function' should be a function mapping a date and an hour
    range (2-tuple of integers in [0,23]) to a Decimal representing energy used
    during that time.'''
    # get identifiers of all shadow registers in reebill from mongo
    registers = get_shadow_register_data(reebill)

    # now that a list of shadow registers are initialized, accumulate energy
    # into them for the specified date range
    for register in registers:
        # service date range
        begin_date = register['prior_read_date'] # inclusive
        end_date = register['present_read_date'] # exclusive

        # get service type of this register (gas or electric)
        # TODO replace this ugly hack with something better
        # (and probably make it a method of MongoReebill)
        service_of_this_register = None
        for service in reebill.services:
            for register_dict in reebill.shadow_registers(service):
                if register_dict['identifier'] == register['identifier']:
                    service_of_this_register = service
                    break
        assert service_of_this_register is not None
        
        # reset register in case energy was previously accumulated
        register['quantity'] = 0

        for day in dateutils.date_generator(begin_date, end_date):
            # the hour ranges during which we want to accumulate energy in this
            # shadow register is the entire day for normal registers, or
            # periods given by 'active_periods_weekday/weekend/holiday' for
            # time-of-use registers
            # TODO make this a method of MongoReebill
            hour_ranges = None
            if 'active_periods_weekday' in register:
                # a tou register should have all 3 active_periods_... keys
                assert 'active_periods_weekend' in register
                assert 'active_periods_holiday' in register
                hour_ranges = map(tuple,
                        register['active_periods_' + dateutils.get_day_type(day)]) 
            else:
                hour_ranges = [(0,23)]

            energy_today = None
            for hourrange in hour_ranges:
                # 5 digits after the decimal points is an arbitrary decision
                # TODO decide what our precision actually is: see
                # https://www.pivotaltracker.com/story/show/24088787
                energy_today = energy_function(day, hourrange)
                
                # convert units from BTU to kWh (for electric) or therms (for gas)
                if register['quantity_units'].lower() == 'kwh':
                    #energy_today /= 3412.14
                    # energy comes out in kwh
                    pass
                elif register['quantity_units'].lower() == 'therms':
                    energy_today /= 100000
                else:
                    raise Exception('unknown energy unit %s' % register['quantity_units'])

                print 'register %s accumulating energy %s %s' % (
                        register['identifier'], energy_today,
                        register['quantity_units'])
                register['quantity'] += energy_today

        # update the reebill: put the total skyline energy in the shadow register
        reebill.set_shadow_register_quantity(register['identifier'],
                register['quantity'])



