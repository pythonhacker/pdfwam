""" Run WCAG unit tests using test files """

import unittest
from pdfchecker import checkAcc

class Mixin:

    def check_for_test(self, response, test_id):
        for item in response['result']:
            if item['Test'] == test_id:
                return item['Status'], item['Description']
        return None,None
            
class TestWcag(unittest.TestCase, Mixin):
    
    def test_wcag_01(self):
        ret = checkAcc('testfiles/wcag.pdf.01/images-with-and-without-ALT.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.01')
        self.assertEqual(stat, {'Fail': 1, 'Pass': 1})

        ret = checkAcc('testfiles/wcag.pdf.01/images-with-and-without-ALT_multipage.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.01')
        self.assertEqual(stat, {'Fail': 1, 'Pass': 3})

    def test_wcag_02(self):
        ret = checkAcc('testfiles/wcag.pdf.02/doc_with_bookmarks.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.02')
        self.assertEqual(stat, 'Pass')
        ret = checkAcc('testfiles/wcag.pdf.02/doc_without_bookmarks.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.02')
        self.assertEqual(stat, 'Fail')

    def test_wcag_04(self):
        ret = checkAcc('testfiles/wcag.pdf.04/decorative-image.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.04')
        self.assertEqual(stat, {'Fail': 0, 'Pass': 1})
        ret = checkAcc('testfiles/wcag.pdf.04/decorative_image_multiple.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.04')
        self.assertEqual(stat, {'Fail': 0, 'Pass': 7})        
        ret = checkAcc('testfiles/wcag.pdf.04/no_decorative_image.pdf',
                       json_value=True, verbose=True)
        # This is a failure
        stat, _ = self.check_for_test(ret, 'wcag.pdf.04')
        self.assertEqual(stat, None)

    def test_egovmon_05(self):
        ret = checkAcc('testfiles/egovmon.pdf.05/encrypted_but_pass.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'egovmon.pdf.05')
        self.assertEqual(stat, 'Pass')
        ret = checkAcc('testfiles/egovmon.pdf.05/encrypted_but_pass2.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'egovmon.pdf.05')
        self.assertEqual(stat, 'Pass')
        ret = checkAcc('testfiles/egovmon.pdf.05/failure1.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'egovmon.pdf.05')
        self.assertEqual(stat, 'Fail')
        ret = checkAcc('testfiles/egovmon.pdf.05/failure2.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'egovmon.pdf.05')
        self.assertEqual(stat, 'Fail')

    def test_wcag_06(self):
        ret = checkAcc('testfiles/wcag.pdf.06/single_table_tagged.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.06')
        self.assertEqual(stat, {'Fail': 0, 'Pass': 1})
        ret = checkAcc('testfiles/wcag.pdf.06/single_table_untagged.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.06')
        self.assertEqual(stat, None)        
        ret = checkAcc('testfiles/wcag.pdf.06/many_tables_tagged.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.06')
        self.assertEqual(stat, {'Fail': 0, 'Pass': 59})

    def test_wcag_pdf_09(self):
        ret = checkAcc('testfiles/wcag.pdf.09/single_page_header_pass.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.09')
        self.assertEqual(stat, 'Pass')
        ret = checkAcc('testfiles/wcag.pdf.09/single_page_header_fail.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.09')
        self.assertEqual(stat, 'Fail')        
        ret = checkAcc('testfiles/wcag.pdf.09/multiple_pages_header_fail.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.09')
        self.assertEqual(stat, 'Fail')
        ret = checkAcc('testfiles/wcag.pdf.09/header_fail_no_tag.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.09')
        self.assertEqual(stat, 'Pass')

    def test_wcag_pdf_12(self):
        ret = checkAcc('testfiles/wcag.pdf.12/test_pass.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.12')
        self.assertEqual(stat, 'Pass')
        # This document has no forms so return is None
        ret = checkAcc('testfiles/wcag.pdf.14/header_footer_pass.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.12')
        self.assertEqual(stat, None)                

    def test_wcag_pdf_15(self):
        ret = checkAcc('testfiles/wcag.pdf.15/form_complete.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.15')
        self.assertEqual(stat, 'Pass')

    def test_wcag_pdf_16(self):
        ret = checkAcc('testfiles/wcag.pdf.16/lang_has_tags_pass.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.16')
        self.assertEqual(stat, 'Pass')                
        ret = checkAcc('testfiles/wcag.pdf.16/lang_no_tags_fail.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.16')
        self.assertEqual(stat, 'Fail')
        ret = checkAcc('testfiles/wcag.pdf.16/lang_no_tags_pass.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.16')
        self.assertEqual(stat, 'Pass')                        

    def test_wcag_pdf_17(self):
        ret = checkAcc('testfiles/wcag.pdf.17/page_numbers_pass.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.17')
        self.assertEqual(stat, 'Pass')
        ret = checkAcc('testfiles/wcag.pdf.17/page_labels_not_applicable.pdf',
                       json_value=True, verbose=True)
        # Document doesn't have pagelabels so None is returned
        stat, _ = self.check_for_test(ret, 'wcag.pdf.17')
        self.assertEqual(stat, None)

    def test_wcag_pdf_18(self):
        ret = checkAcc('testfiles/wcag.pdf.18/title_pass.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.18')
        self.assertEqual(stat, 'Pass')
        ret = checkAcc('testfiles/wcag.pdf.18/title_fail.pdf',
                       json_value=True, verbose=True)
        stat, _ = self.check_for_test(ret, 'wcag.pdf.18')
        self.assertEqual(stat, 'Fail')                
        
if __name__ == "__main__":
    unittest.main()
        
