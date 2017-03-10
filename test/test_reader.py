# coding=utf-8


import unittest
import mimircache.c_cacheReader as c_cacheReader
from mimircache.cacheReader.csvReader import csvReader
from mimircache.cacheReader.plainReader import plainReader
from mimircache.cacheReader.vscsiReader import vscsiReader

DAT_FOLDER = "../data/"
import os
if not os.path.exists(DAT_FOLDER):
    if os.path.exists("data/"):
        DAT_FOLDER = "data/"
    elif os.path.exists("../mimircache/data/"):
        DAT_FOLDER = "../mimircache/data/"


class cReaderTest(unittest.TestCase):
    def test_reader_vscsi(self):
        reader = c_cacheReader.setup_reader("{}/trace.vscsi".format(DAT_FOLDER), 'v')
        lines = c_cacheReader.get_num_of_lines(reader)
        self.assertEqual(lines, 113872)

        first_request = c_cacheReader.read_one_element(reader)
        self.assertEqual(int(first_request), 42932745 + 1)              # +1 is to avoid block 0

        c_cacheReader.reset_reader(reader)
        first_request = c_cacheReader.read_one_element(reader)
        self.assertEqual(int(first_request), 42932745 + 1)
        c_cacheReader.close_reader(reader)


    def test_reader_plain(self):
        reader = c_cacheReader.setup_reader("{}/trace.txt".format(DAT_FOLDER), 'p')
        lines = c_cacheReader.get_num_of_lines(reader)
        self.assertEqual(lines, 113872)
        first_request = c_cacheReader.read_one_element(reader)
        self.assertEqual(int(first_request), 42932745)

        c_cacheReader.reset_reader(reader)
        first_request = c_cacheReader.read_one_element(reader)
        self.assertEqual(int(first_request), 42932745)
        c_cacheReader.close_reader(reader)


    def test_reader_csv(self):
        reader = c_cacheReader.setup_reader("{}/trace.csv".format(DAT_FOLDER), 'c', data_type='c',
                                            init_params={"header":True, "delimiter":",", "label_column":5, "size_column":4})
        lines = c_cacheReader.get_num_of_lines(reader)
        self.assertEqual(lines, 113872)
        first_request = c_cacheReader.read_one_element(reader)
        self.assertEqual(int(first_request), 42932745)

        c_cacheReader.reset_reader(reader)
        first_request = c_cacheReader.read_one_element(reader)
        self.assertEqual(int(first_request), 42932745)
        c_cacheReader.close_reader(reader)


    def test_reader_binary(self):
        reader = c_cacheReader.setup_reader("{}/trace.vscsi".format(DAT_FOLDER), 'b', data_type='l',
                                            init_params={"label":6, "real_time":7, "fmt": "<3I2H2Q"})
        lines = c_cacheReader.get_num_of_lines(reader)
        self.assertEqual(lines, 113872)
        first_request = c_cacheReader.read_one_element(reader)
        self.assertEqual(int(first_request), 42932745)

        c_cacheReader.reset_reader(reader)
        first_request = c_cacheReader.read_one_element(reader)
        self.assertEqual(int(first_request), 42932745)
        c_cacheReader.close_reader(reader)


    def test_context_manager(self):
        with vscsiReader("{}/trace.vscsi".format(DAT_FOLDER)) as reader:
            self.assertEqual(reader.get_num_of_total_requests(), 113872)



class readerTest(unittest.TestCase):
    def test_reader_v(self):
        pass


if __name__ == "__main__":
    unittest.main()

