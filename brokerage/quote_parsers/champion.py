from tablib import formats

from util.dateutils import date_to_datetime
from util.monthmath import Month
from brokerage.brokerage_model import MatrixQuote
from brokerage.quote_parser import excel_number_to_datetime, QuoteParser


class ChampionMatrixParser(QuoteParser):
    """ Parser for Champion Matrix Rates
    """

    FILE_FORMAT = formats.xls

    HEADER_ROW = 13
    VOLUME_RANGE_COL = 'H'
    QUOTE_START_ROW = 14
    QUOTE_END_ROW = 445
    RATE_CLASS_COL = 'F'
    EDC_COL = 'E'
    DESCRIPTION_COL = 'G'
    TERM_START_COL = 'I'
    TERM_END_COL = 'L'
    PRICE_START_COL = 'I'
    PRICE_END_COL = 'K'
    STATE_COL = 'D'
    START_DATE_COL = 'C'

    EXPECTED_SHEET_TITLES = [
        'PA',
        'OH',
        'IL',
        'NJ',
        'MD'
    ]

    VALIDITY_DATE_CELL = ('PA', 8, 'C', None)

    def _extract_volume_range(self, sheet,row, col):
        regex = r'(\d+)-(\d+) MWh'
        low, high = self._reader.get_matches(sheet, row, col, regex,
                                             (int, int))
        if low % 10 == 1:
            low -= 1
        return low * 1000, high * 1000

    def _extract_quotes(self):
        for sheet in self.EXPECTED_SHEET_TITLES:

            for row in xrange(self.QUOTE_START_ROW,
                              self._reader.get_height(sheet)):
                state = self._reader.get(sheet, row, self.STATE_COL,
                                         basestring)
                if state == '':
                    continue

                edc = self._reader.get(sheet, row, self.EDC_COL,
                                         basestring)

                description = self._reader.get(sheet, row,self.DESCRIPTION_COL,
                                         basestring)

                rate_class_name = self._reader.get(sheet, row,
                    self.RATE_CLASS_COL, basestring)
                rate_class_alias = '-'.join(
                    [state, edc, rate_class_name, description])

                start_from = excel_number_to_datetime(self._reader.get(
                    sheet, row, self.START_DATE_COL, float))

                start_until = date_to_datetime((Month(start_from) + 1).first)

                min_volume, limit_volume = self._extract_volume_range(sheet,row,
                                                        self.VOLUME_RANGE_COL)

                for col in self._reader.column_range(self.TERM_START_COL,
                                                     self.TERM_END_COL):
                    price = float(self._reader.get(sheet, row, col,
                                                  (float, basestring,
                                                   type(None))))/1000

                    term = self._reader.get_matches(
                                            sheet, self.HEADER_ROW, col,
                                            '(\d+) mths', int)

                    for rate_class_id in self.get_rate_class_ids_for_alias(
                            rate_class_alias):
                        quote = MatrixQuote(start_from=start_from,
                            start_until=start_until, term_months=term,
                            valid_from=self._valid_from,
                            valid_until=self._valid_until,
                            min_volume=min_volume,
                            limit_volume=limit_volume,
                            purchase_of_receivables=False, price=price,
                            rate_class_alias=rate_class_alias)
                        # TODO: rate_class_id should be determined automatically
                        # by setting rate_class
                        if rate_class_id is not None:
                            quote.rate_class_id = rate_class_id
                        yield quote
