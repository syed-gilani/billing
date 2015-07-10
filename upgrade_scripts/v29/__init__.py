"""Upgrade script for version 29.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
from brokerage.brokerage_model import MatrixQuote, CompanyPGSupplier
from core.extraction import Field, TextExtractor
from core.extraction.applier import Applier
from core.model import Supplier, Utility, AltitudeSession

from core import init_model, init_altitude_db
from core.model import Session
from upgrade_scripts import alembic_upgrade


def insert_matrix_file_names(s):
    de = s.query(Supplier).filter_by(name='direct energy').one()
    de.matrix_file_name = 'directenergy.xls'
    aep = s.query(Supplier).filter_by(name='AEP').one()
    aep.matrix_file_name = 'aep.xls'
    usge = s.query(Supplier).filter_by(name='USG&E').one()
    usge.matrix_file_name = 'usge.xls'

def create_extractors(s):
    date_format = r'[A-Za-z]+\s*[0-9]{1,2},\s*[0-9]{4}'
    num_format = r'[0-9,\.]+'
    start_regex = 'Your electric bill - [A-Za-z]+ [0-9]{4}for the period (%s)' % date_format
    end_regex = 'Your electric bill - [A-Za-z]+ [0-9]{4}for the period %s to (%s)' % (date_format, date_format)
    energy_regex = r'.*([0-9]{4})Your next meter'
    next_meter_read_regex = r'.*Your next meter reading is scheduled for (%s)' % date_format
    e =  TextExtractor(name='Original Pepco Extractor')
    e.fields.append(TextExtractor.TextField(regex=start_regex, type=Field.DATE, applier_key=Applier.START))
    e.fields.append(TextExtractor.TextField(regex=end_regex, type=Field.DATE, applier_key=Applier.END))
    e.fields.append(TextExtractor.TextField(regex=energy_regex, type=Field.FLOAT, applier_key=Applier.ENERGY))
    e.fields.append(TextExtractor.TextField(regex=next_meter_read_regex, type=Field.DATE, applier_key=Applier.NEXT_READ))

    #pepco bills from 2015, with banner
    pep_start_regex = 'your electric bill for the period\s*(%s) to %s' % (date_format, date_format)
    pep_end_regex = 'your electric bill for the period\s*%s to (%s)' % (date_format, date_format)
    pep_energy_regex = r'Use \(kWh\)\s+(%s)' % num_format
    pep_next_meter_read_regex = r'Your next meter reading is scheduled for (%s)' % date_format
    pep_charges_regex = r'(Distribution Services:.*?(?:Status of your Deferred|Page)(?:.*?)Transmission Services\:.*?Energy Usage History)'
    pep_rate_class_regex = r'Details of your electric charges(.*?)\s+-\s+service number'
    pepco_2015 = TextExtractor(name="Extractor for Pepco bills in 2015 id 18541")
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_start_regex, type=Field.DATE, applier_key=Applier.START))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_end_regex, type=Field.DATE, applier_key=Applier.END))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_energy_regex, type=Field.FLOAT, applier_key=Applier.ENERGY))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_next_meter_read_regex, type=Field.DATE, applier_key=Applier.NEXT_READ))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_charges_regex, type=Field.PEPCO_NEW_CHARGES, applier_key=Applier.CHARGES))
    pepco_2015.fields.append(TextExtractor.TextField(regex=pep_rate_class_regex, type=Field.STRING, applier_key=Applier.RATE_CLASS))

    #pepco bills from before 2015, blue logo
    pep_old_start_regex = r'Services for (%s) to %s' % (date_format, date_format)
    pep_old_end_regex = r'Services for %s to (%s)' % (date_format, date_format)
    pep_old_energy_regex = r'KWH\s*Used\s+(\d+)'
    pep_old_next_meter_read_regex = r'.Your next scheduled meter reading is (%s)' % date_format
    pep_old_charges_regex = r'(distribution services.*?current charges this period)'
    pep_old_rate_class_regex = r'Meter Reading Information[A-Z0-9]*\s+(.*)The present reading'
    pepco_old = TextExtractor(name='Pepco bills from before 2015 with blue logo id 2631')
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_start_regex, type=Field.DATE, applier_key=Applier.START))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_end_regex, type=Field.DATE, applier_key=Applier.END))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_energy_regex, type=Field.FLOAT, applier_key=Applier.ENERGY))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_next_meter_read_regex, type=Field.DATE, applier_key=Applier.NEXT_READ))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_charges_regex, type=Field.PEPCO_OLD_CHARGES, applier_key=Applier.CHARGES))
    pepco_old.fields.append(TextExtractor.TextField(regex=pep_old_rate_class_regex, type=Field.STRING, applier_key=Applier.RATE_CLASS))

    #washington gas bills
    wg_start_regex = r'(%s)-%s\s*\(\d+ Days\)' % (date_format, date_format)
    wg_end_regex = r'%s-(%s)\s*\(\d+ Days\)' % (date_format, date_format)
    wg_energy_regex = r"Distribution Charge\s+(%s)" % num_format
    wg_next_meter_read_regex = r'Your next meter reading date is (%s)' % date_format
    wg_charges_regex = r'(DISTRIBUTION SERVICE.*?(?:Total Washington Gas Charges This Period|the easiest way to pay))'
    wg_rate_class_regex = r'rate class:\s+meter number:\s+([^\n]+)'
    washington_gas = TextExtractor(name='Extractor for Washington Gas bills with green and yellow and chart id 15311')
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_start_regex, type=Field.DATE, applier_key=Applier.START))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_end_regex, type=Field.DATE, applier_key=Applier.END))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_energy_regex, type=Field.FLOAT, applier_key=Applier.ENERGY))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_next_meter_read_regex, type=Field.DATE, applier_key=Applier.NEXT_READ))
    washington_gas.fields.append(TextExtractor.TextField(regex=wg_charges_regex, type=Field.WG_CHARGES, applier_key=Applier.CHARGES))
    washington_gas.fields.append(TextExtractor.TextField(
        regex=wg_rate_class_regex, type=Field.STRING, applier_key=Applier.RATE_CLASS))
    s.add_all([e, pepco_2015, pepco_old, washington_gas])

def create_charge_name_maps(s):
    wg = s.query(Utility).filter_by(name='washington gas').one()
    wg.charge_name_map = {
        'Distribution Charge': 'DISTRIBUTION_CHARGE',
        'Customer Charge': 'CUSTOMER_CHARGE',
        'PGC': 'PGC',
        'Peak Usage Charge': 'PEAK_USAGE_CHARGE',
        'DC Rights-of-Way Fee': 'RIGHT_OF_WAY',
        'Sustainable Energy Trust Fund': 'SETF',
        'Energy Assistance Trust Fund': 'EATF',
        'Delivery Tax': 'DELIVERY_TAX',
        'Sales Tax': 'SALES_TAX',
    }

    pepco = s.query(Utility).filter_by(name='pepco').one()
    pepco.charge_name_map = {
        'Customer Charge':'CUSTOMER_CHARGE',
        'Energy Charge':'ENERGY_CHARGE',
        'Grid Resiliency Charge':'GRID_RESILIENCY_CHARGE',
        'Franchise Tax (Delivery)':'DELIVERY_TAX',
        'Universal Service Charge':'UNIVERSAL_SERVICE_CHARGE',
        'Gross Receipts Tax':'GROSS_RECEIPTS_TAX',
    }

def upgrade():
    alembic_upgrade('49b8d9978d7e')

    init_model()
    init_altitude_db()
    s, a = Session(), AltitudeSession()

    create_extractors(s)
    create_charge_name_maps(s)

    a.bind.url.drivername
    insert_matrix_file_names(s)
    for supplier in a.query(CompanyPGSupplier).all():
        s.merge(supplier)
    if str(a.bind.url).startswith('mssql'):
        a.execute('create view Rate_Class_View as select * from Rate_Class')

    s.commit()
    a.commit()
