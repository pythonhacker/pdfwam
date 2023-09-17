# -- coding: utf-8
#
# Copyright (C) Tingtun AS 2013.
#

import pdfStructureMixin
import PyPDF2.generic as generic
import re
import collections

class PdfWCAG(pdfStructureMixin.PdfStructureMixin):
    """ This class implements those PDF tests and techniques
    as advocated by WCAG 2.0. It is derived from PdfStructureMixin
    so as to inherit the already existing PDF-WAM behaviour """

    # All the functions of this class have the following
    # return values
    #
    # 0 -> test failed
    # 1 -> test passed
    # 2 -> test not applicable
    
    # In most cases, a return value of 2 can be considered
    # as a failure, however the distinction should be made
    # by the caller, not by this class.

    # Supported test IDs
    test_ids = ('WCAG.PDF.04', 'WCAG.PDF.06', 'WCAG.PDF.12',
                'WCAG.PDF.15', 'WCAG.PDF.17', #'WCAG.PDF.14',
                'WCAG.PDF.03')

    # Those tests which fill in their own WAM entries
    independent_test_ids = ('WCAG.PDF.11.13',)

    # Test id descriptions - this is for printing the report
    test_id_desc = {'egovmon.pdf.03': 'structure tree',
                    'egovmon.pdf.05': 'permissions',
                    'egovmon.pdf.08': 'scanned',
                    'wcag.pdf.01': 'alt text for images',
                    'wcag.pdf.02': 'bookmarks',
                    'wcag.pdf.03': 'tab and reading order',                    
                    'wcag.pdf.04': 'artifact images',
                    'wcag.pdf.06': 'accessible tables',
                    'wcag.pdf.12': 'forms name/role/value',
                    'wcag.pdf.09': 'consistent headers',
                    'wcag.pdf.18': 'title',
                    'wcag.pdf.16': 'natural language',
                    'wcag.pdf.sc244': 'accessible external links',
                   # 'wcag.pdf.14': 'running headers/footers',
                    'wcag.pdf.15': 'submit buttons in forms',
                    'wcag.pdf.17': 'consistent page-numbers' }
                
    def __init__(self, verbose=True):
        pdfStructureMixin.PdfStructureMixin.__init__(self)
        self.verbose = verbose

    def get_json(self):

        json = {
            'result' : [],
            'summary' : {},
        }

        # Pre-preparation for wcag.pdf.11 and wcag.pdf.13
        if ('wcag.pdf.11' in self.memo) or ('wcag.pdf.13' in self.memo):
            f11, p11 = self.memo['wcag.pdf.11']
            f13, p13 = self.memo['wcag.pdf.13']
            # Fail is the min of fails, pass is the max of passes
            fail = min(f11, f13)
            succ = max(p11, p13)
            # Add an sc244 entry
            self.memo['wcag.pdf.sc244'] = (fail, succ)
            del self.memo['wcag.pdf.11']
            del self.memo['wcag.pdf.13']

        tfail, tpass = 0, 0

        for test_name, test_status in self.memo.items():

            msg = ''

            if test_status in (0, 1):
                if test_status == 0:
                    msg = 'Fail'
                    tfail += 1
                elif test_status == 1:
                    msg = 'Pass'
                    tpass += 1
            elif test_status == '':
                msg = 'Fail'
                tfail += 1
            elif type(test_status) is tuple:
                fail, succ = test_status
                tfail += fail
                tpass += succ

                msg = {'Fail' : fail, 'Pass' : succ}

            descr = self.test_id_desc.get(test_name, 'N.A')

            json['result'].append({'Test': test_name, 'Status': msg, 'Description': descr})

        json['summary'] = {'Total' : (tfail + tpass), 'Fail' : tfail, 'Pass' : tpass}

        return json

    def print_report(self):
        """ Print a report of the tests run and their status """

        # Pre-preparation for wcag.pdf.11 and wcag.pdf.13
        if ('wcag.pdf.11' in self.memo) or ('wcag.pdf.13' in self.memo):
            f11, p11 = self.memo['wcag.pdf.11']
            f13, p13 = self.memo['wcag.pdf.13']
            # Fail is the min of fails, pass is the max of passes
            fail = min(f11, f13)
            succ = max(p11, p13)
            # Add an sc244 entry
            self.memo['wcag.pdf.sc244'] = (fail, succ)
            del self.memo['wcag.pdf.11']
            del self.memo['wcag.pdf.13']
            
        print('\n***Test Report***')
        
        print('-'*80)
        print('TEST'.ljust(30) + '|' + ' STATUS'.ljust(20) + ' |' + ' DESCRIPTION')
        print('-'*80)

        tfail, tpass = 0,0
        for test_name, test_status in self.memo.items():
            s = test_name.ljust(30)
            print(s + '|', end=' ')
            if test_status in (0, 1):
                if test_status==0:
                    msg='Fail'
                    tfail += 1
                elif test_status==1:
                    msg='Pass'
                    tpass += 1
            elif test_status == '':
                msg='Fail'
                tfail += 1                
            elif type(test_status) is tuple:
                fail, succ = test_status
                msg = 'Fail:%d,' % fail + 'Pass:%d' % succ
                tfail += fail
                tpass += succ
                
            msg = msg.ljust(20)
            print(msg + '|', end=' ')
            descr = self.test_id_desc.get(test_name, 'N.A')
            print(descr)
            
        print('-'*80)
        print('Test summary: %d total tests, %d fail, %d pass' % (tfail+tpass, tfail, tpass))
        
    def runAll(self):
        """ Wrapper method for running all wcag 2.0 tests """

        results = {}

        for name in dir(self):
            if name.startswith('test_WCAG'):
                func = getattr(self, name)
                ret = func()
                results[name] = ret

        return results

    def runSelectedTest(self, test_id, results):
        """ Run a specific test, given the test id """

        if test_id in self.test_ids:
            func_name = 'test_' + test_id.replace('.', '_')
            egov_test_id = 'EGOVMON.A.' + test_id

            try:
                func = getattr(self, func_name)
                ret = func()
                if (type(ret) is int) and ret != 2:
                    # Test produced either 0 or 1
                    results[egov_test_id] = {(0,1): int(ret)}
                    self.memo[test_id.lower()] = ret
                elif type(ret) is dict:
                    # Two tuple where first element is the
                    # number of successes and 2nd element
                    # number of failures
                    results[egov_test_id] = {}
                    count = 1
                    fail, succ = 0, 0
                    
                    for status, pagedict in ret.items():
                        for page, items in pagedict.items():
                            for item in items:
                                results[egov_test_id][(page, count)] = status
                                if status: succ += 1
                                else: fail += 1
                                count += 1

                    self.memo[test_id.lower()] = (fail, succ)
            except AttributeError:
                pass
            
        elif test_id in self.independent_test_ids:
            func_name = 'test_' + test_id.replace('.', '_')

            try:
                func = getattr(self, func_name)
                ret = func(results)
                # Nothing to do with ret, since function is independent
            except AttributeError:
                pass
            
    def runAllTests(self):
        """ Run all PDF WAM tests """

        self.initAWAM()
        self.processAWAM()
        results = self.awamHandler.resultMap

        for test_id in self.test_ids:
            self.runSelectedTest(test_id, results)

        for test_id in self.independent_test_ids:
            func_name = 'test_' + test_id.replace('.', '_')

            try:
                func = getattr(self, func_name)
                keys1 = set(results.keys())
                ret = func(results)
                keys2 = set(results.keys())

                # Get the diff
                new_keys = list(keys2 - keys1)

                for key in new_keys:
                    val = results[key]

                    test_id = key.replace('EGOVMON.A.','').lower()
                    if (type(val) is int) and val != 2:
                        # Test produced either 0 or 1
                        self.memo[test_id] = val
                    elif type(val) is dict:
                        # print 'VAL=>',val
                        fail, succ = 0, 0
                        
                        for (page, count), status in val.items():
                            if status: succ += 1
                            else: fail += 1
                            self.memo[test_id] = (fail, succ)                                    
                        
                # Nothing to do with ret, since function is independent
            except AttributeError:
                pass
        
        return results

    def updateResult(self, result, pg, target=None):
        """ Update result for page 'pg' with target 'target' """

        try:
            x=result[pg]
        except KeyError:
            result[pg]=[target]
            return
        
        try:
            result[pg].index(target)
        except ValueError:
            result[pg].append(target)            

    def initResult(self):
        return {0: {}, 1: {}}
    
    def test_WCAG_PDF_17(self):
        """ This tests consistent page numbering across
        PDF page viewer controls and the PDF document.
        This is test #17 in WCAG 2.0 """

        pl = self.getPageLabels()
        # If no '/PageLabels' dictkey found, we
        # cannot validate this test, so return N.A
        if pl==None:
            self.logger.info('No /PageLabels dictionary found in Document')
            return 2

        try:
            numsDict = pl['/Nums']
        except KeyError:
            self.logger.error("Error: Invalid PageLabels dictionary, no '/Nums' key found!")
            return 0

        # This list should have even number of elements
        # else fail
        if len(numsDict) % 2 != 0:
            self.logger.error("Error: Invalid PageLabels dictionary, length is not multiple of 2")
            return 0
        
        # Convert the pagelabels nums dictionary to
        # a Python dictionary
        numsd, numsl = {}, []
        idx = 0

        for item in numsDict:
            if idx % 2 == 0:
                l = [item]
            else:
                l.append(item)
                numsl.append(l[:])
                
            idx += 1

        numsd = dict(numsl)
        # There should be a key for 0
        if 0 not in list(numsd.keys()):
            self.logger.error("Error: Invalid PageLabels dictionary, key '0' not found!")
            return 0

        # Validate each entry
        for item in list(numsd.values()):
            obj = item.get_object()
            # There should be an /S key which has any of the following
            # values - ['/D', '/r', '/R', '/A', '/a']
            try:
                sval = obj['/S']
            except KeyError:
                self.logger.error("Error: Invalid PageLabels entry",obj,"key '/S' doesn't exist!")
                return 0

            if sval not in ('/D','/r','/R','/A','/a'):
                self.logger.error("Error: Invalid PageLabels entry",obj,"key '/S' has invalid value =>",sval)
                return 0                

        self.logger.info('wcag.pdf.17 - Test passed')
        return 1

    def test_WCAG_PDF_11_13(self, wamdict):
        """ Test if hyperlinks and text associated with them
        are accessible. This is test #11 in PDF WCAG 2.0
        techniques

        This also tests whether '/Link' artifacts have
        'Alt' representations. This is test #13 in WCAG 2.0

        """

        # In PDF, link annotations are associated to a geometric
        # region, rather than a particular object in the
        # content-stream. Hence link annotations alone are
        # not useful for users with visual impairements.

        # Instead, PDF document that are tagged can provide
        # the link between content items and link annotations
        # thus making links accessible, if a "Link" annotation
        # is added the right way.

        # Hence by definition of this test, if the document
        # is missing tags, this test is an automatic failure.

        # If there are no external links, the test isn't
        # applicable.

        if not self.hasExternalLinks():
            return 2

        # Has external links, but no tags
        if (self.structroot == None) or (len(self.structroot) == 0):
            # Struct-tree is not needed for WCAG13 but is needed for WCAG11
            # so if not present, the combined test cant be applied
            self.logger.info('Skiping test WCAG_11_13 because struct tree is absent or empty!')
            return 0

        # For every link in external links, check if it has
        # a link annotation object in the tags tree with the
        # requisite information.
        linkObjs = [x[0] for x in list(self.awamHandler.linkAnnots.values())]
        # All link objects should be present in above list,
        # otherwise test fails.

        # Element count
        count = 0

        # Intialize entries
        wamdict['EGOVMON.A.WCAG.PDF.11']={}
        wamdict['EGOVMON.A.WCAG.PDF.13']={}
        
        for extLink, pg in self.fetchExternalLinks():
            count += 1

            # import pdb; pdb.set_trace()
            
            try:
                a = extLink['/A'].get_object()
                linkUri = a['/URI']
            except KeyError:
                # Do this only for external links, not for any
                # internal links (links to other parts of the
                # document). Internal links dont have /URI key.
                continue
            
            if extLink not in linkObjs:
                try:
                    # NOTE: The pyPdf sometimes does a wrong job
                    # of associating a structure artifact to a page
                    # so the page number here might sometimes be
                    # wrong. (Example: tests/extlinks/lesson5.pdf)
                    self.logger.error("Error: Link [%s] doesn't have a corresponding link annotation object (pg: %d)" % (linkUri, pg.num+1))
                    # fail the test
                    wamdict['EGOVMON.A.WCAG.PDF.11'][(pg.num+1, count)] = 0
                except KeyError:
                    pass
            else:
                # Verify the link object is proper
                # (defines a Rect and a URI)
                try:
                    rect=extLink['/Rect']
                    uri=extLink['/A']
                    self.logger.debug("Link [%s] HAS a corresponding link annotation object (pg: %d)" % (linkUri, pg.num+1))
                    wamdict['EGOVMON.A.WCAG.PDF.11'][(pg.num+1, count)] = 1
                except KeyError:
                    # fail the test
                    wamdict['EGOVMON.A.WCAG.PDF.11'][(pg.num+1, count)] = 0                    

            # Now for Alt test
            try:
                alt=extLink['/Alt']
                if not alt:
                    self.logger.debug('Error: Null /Alt entry found for Link [%s], (pg: %d)' % (linkUri, pg.num+1))
                    wamdict['EGOVMON.A.WCAG.PDF.13'][(pg.num+1, count)] = 0
                else:
                    wamdict['EGOVMON.A.WCAG.PDF.13'][(pg.num+1, count)] = 1
                    self.logger.debug('ALT Key is good for Link [%s], (pg: %d)' % (linkUri, pg.num+1))
            except KeyError:
                self.logger.debug('Error: No /Alt key found for Link [%s], (pg: %d)' % (linkUri, pg.num+1))
                # Failed
                wamdict['EGOVMON.A.WCAG.PDF.13'][(pg.num+1, count)] = 0                                        

        # Nothing to return since we are modifying wamdict in place
        return 1

    def test_WCAG_PDF_12(self):
        """ This test checks whether every form field
        has been assigned the appropriate name/role/value triple.
        This is test #12 of WCAG-2.0 PDF techniques """
        
        # We need to follow the N/R/V table specified in
        # http://www.w3.org/WAI/GL/WCAG20-TECHS/pdf.html#PDF12
        # to the word, for this test. Since each type of
        # form control has different ways of accessing these
        # fields, they have to be coded separately.

        form = self.getFormObject()
        
        # No forms found, test not applicable
        if form is None:
            self.logger.info('No Form object found in Document')
            return 2

        # import pdb;pdb.set_trace()
        types = collections.defaultdict(int)
        for item in self.fetchFormFields(form):
            try:
                ffield = item.get_object()
                types[ffield['/FT']] += 1
            except:
                pass

        print('All form field types =>', types)
        for item in self.fetchFormFields(form):
            # print 'Item=>',item
            
            # The set of rules given for this test are
            # quite involved. However it can be split
            # to the following cascading rules.
            ffield = item.get_object()
            # print ffield

            # Consider only leaf elements (skip if '/Kids' found)
            try:
                ffield['/Kids']
                continue
            except KeyError:
                pass
        
            # 1. Every field ought to have an identifying
            # role (type). This is set by the '/FT' field.
            # It has got to be a supported type.
            try:
                frole = ffield['/FT']
            except KeyError:
                self.logger.debug("Error: Failed to find role for form-field object #%d" % (item.idnum))
                # Most probably not a form field object we need to worry about
                continue

            if not frole in self.form_elems:
                self.logger.debug("Error: Form element type '%s' not a known role" % frole)
                return 0

            # Skip buttons - fix for issue #28 - false positive for form fields
            if frole == '/Btn':
            #    # print('Skipping', ffield)
                continue
                # import pdb;pdb.set_trace()

            #if frole == '/Ch':
            #    import pdb;pdb.set_trace()

            # UPDATE - Since we are not looking for a name for
            # push buttons, this code is not quite valid.
            
            # 2. Every form element should have a name
            # that can be read by accessibility software. This
            # is indicated either by the '/TU' field or by
            # the '/CA' field (only in case of pushbuttons).
            # try:
            #     name = ffield['/TU']
            # except KeyError:
            #     try:
            #         name = ffield['/CA']
            #     except KeyError:
            #         try:
            #             # Finding this format in some PDFs.
            #             # not sure if this is standard
            #             name = ffield['/MK']['/CA']
            #         except KeyError:
            #             self.logger.debug("Error: Failed to find name for form-field object #%d" % (item.idnum))
            #             import pdb;pdb.set_trace()
            #             # print ffield
            #             return 0

            try:
                name = ffield['/TU']
            except KeyError:
                try:
                    name = ffield['/T']
                    # Some documents use the '/T' field (wrongly) for the name.
                    # we can allow this if this is not equal to "Name"
                    #if name == "Name":
                    #    # false flag key error
                    #    raise KeyError
                except KeyError:
                    self.logger.debug("Error: Failed to find name for form-field object #%d" % (item.idnum))
                    # import pdb;pdb.set_trace()
                    # print ffield
                    return 0                    

            # The name has got to be a valid one
            if not name:
                self.logger.debug("Error: Form field object #%d has null name!" % (item.idnum))
                return 0

            # 3. Every field should have either a value or a state
            # A value can be either a default-value ('/DV') or a user-input
            # value ('/V'). The state is set by the '/Ff' field which should
            # be an integer.
            try:
                if ffield['/V'] or ffield['/DV']:
                    # fine 
                    pass
            except KeyError:
                # some field types like list-box, combo-box
                # or radio buttons can provide values in
                # '/Opt' fields. Check for the /Opt field
                try:
                    if ffield['/Opt']:
                        pass
                except KeyError:
                    # Check for state
                    try:
                        state = ffield['/Ff']
                        # Not a number
                        if type(state) != generic.NumberObject:
                            # Error
                            self.logger.debug("Error: Form field object #%d has wrong state",state)
                            return 0
                    except KeyError:
                        # print ffield
                        self.logger.debug("Error: Form field object #%d has no proper state" % (item.idnum))
                        # Ignore this for the time being
                        # FIXME: Add a strict flag which will make this
                        # an error as well.
                        continue

        self.logger.info('wcag.pdf.12 - Test passed')
        # Everything fine
        return 1
            
    def test_WCAG_PDF_15(self):
        """ Test if a form which submits data has a proper submit button
        with an associated submit action. This is test #15 in PDF-WCAG2.0
        techniques """

        form = self.getFormObject()
        
        # No forms found, test not applicable
        if form==None:
            self.logger.info('No Form object found in Document')
            return 2

        pushbtns = []
        
        for item in self.fetchFormFields(form):
            # Find the submit button
            ffield = item.get_object()
            try:
                state = ffield['/Ff']
                if (state == 65536):
                    # Indicates a push button field
                    tu = ffield['/TU']
                    pushbtns.append([ffield, tu])
                    # print ffield
                    # break
            except KeyError:
                pass

        # import pdb; pdb.set_trace()

        for btn, name in pushbtns:
            # print 'Name=>',btn, name
            try:
                ca = btn['/MK']['/CA']
                # CHECKME: Is this only found for "Send email" type buttons ?
                # print ca                
                return 1
            except:
                # Inspect type of submit (JS or something else)
                try:
                    typ = btn['/S']
                    # Some basic validation for JS type submit
                    if typ.lower() == 'javascript':
                        # Get js element
                        try:
                            js = btn['/JS']
                            # Not doing any JS validation
                        except KeyError:
                            self.logger.debug('Error: Submit type is javascript, but no /JS key found')
                            # Failed
                            return 0
                except KeyError:
                    # submit type is not javascript
                    pass
                
                self.logger.info('wcag.pdf.15 - Test passed (Submit button found)')
                return 1
            else:
                pass
        
        # No submit type button found, test not applicable
        self.logger.info('No Submit type button found in Document')
        return 2

    def test_WCAG_PDF_06(self):
        """ Test if the tables (if any) defined in the PDF
        document are accessible. This is test #6 in PDF-WCAG2.0
        techniques """

        if len(self.awamHandler.tableStructDict) == 0:
            self.logger.info('No tables found in Document')
            # No tables ? test not applicable
            return 2

        results = self.initResult()
        self.logger.debug('No of tables =>',len(self.awamHandler.tableStructDict))

        # Loop through each and see if it is marked invalid
        #if any([x.invalid for x in self.awamHandler.tableStructDict.values()]):
        #    # Failed
        #    print 'Invalid table structure found in Document'            
        #    return 0
        for tbl in list(self.awamHandler.tableStructDict.values()):
            pg = tbl.getPage()
            if tbl.invalid:
                import pdb; pdb.set_trace()
                self.updateResult(results[0], pg, tbl)
            else:
                self.updateResult(results[1], pg, tbl)
                
        self.logger.info('wcag.pdf.06 - Test completed')
        return results

    def test_WCAG_PDF_04(self):
        """ Test if any background image is specified correctly.
        This is test #4 in PDF WCAG 2.0 techniques """

        # Since we have no way of knowing if an image
        # is decorative by inspecting the structure/content,
        # this test does some basic checks on /Artifact
        # type elements which could be images and verifies
        # if they are specified correctly.

        imgRe = re.compile(r'(\/Im\d+)|(\/Fm\d+)')
        imgArtifacts = 0

        results = self.initResult()
        
        for pg in range(len(self.pages)):
            for artifactElems in self.artifactElements(pg):
                # First element is the artifact element
                artifact, artype = artifactElems[0]
                if artype=='BMC':
                    # artifact should be like ['/Artifact']
                    if len(artifact) != 1:
                        # Error
                        self.logger.debug('/Artifact type is BMC, however artifact element',artifact,'has invalid length!')
                        self.updateResult(results[0], pg+1, artifact)
                elif artype=='BDC':
                    # artifact should be like ['/Artifact', {}]
                    if len(artifact) != 2:
                        # Error
                        self.logger.debug('/Artifact type is BMC, however artifact element',artifact,'has invalid length!')
                        self.updateResult(results[0], pg+1, artifact)                        
                # Check if this specifies an image
                operands = [x[0] for x,y in artifactElems[1:] if len(x)>0]
                operands_s = []
                for opr in operands:
                    try:
                        operands_s.append(str(opr))
                    except UnicodeEncodeError:
                        operands_s.append(str(opr))

                if any([imgRe.match(opr) for opr in operands_s]):
                    imgArtifacts += 1
                    self.updateResult(results[1], pg+1)                    

        self.logger.info('Number of img artifacts =>',imgArtifacts)
        self.logger.info("Number of images =>", self.getNumImages())
        self.logger.info("Numer of figure elements =>",len(self.awamHandler.figureEls))
        
        self.nArtifactImgs = imgArtifacts
        
        if imgArtifacts > 0:
            self.logger.info('wcag.pdf.04 - Test passed')
            return results

        self.logger.info('No /Artifact images found in Document')
        # Not applicable
        return 2

    def test_WCAG_PDF_14(self):
        """ Test if the document provides running page headers
        and footers. This is test #14 in PDF WCAG 2.0 techniques 

        # NOTE - This test currently works only for one
        # PDF document - tests/wcag2.0/header-footer/headers-footers-word.pdf
        # Only this document is defining the pagination artifacts
        # in the formal way described in the WCAG 2.0 documentation
        # for this technique.

        # The OO document i.e tests/wcag2.0/header-footer/headers-footers-oo.pdf
        # doesnt define any of these artifacts. Hence not sure how
        # OO embeds this information in the page. Checking the
        # structure elements for the OO document doesn't provide
        # any information.

        # Till this is identified and fixed, this test can be
        # considered as partly implemented. It takes care of
        # one way ot specifying the pagination artifacts but
        # need to find out if there are more ways of doing so.
        """
        
        
        results = self.initResult()
        pgKeys = {}
        
        for pg in range(len(self.pages)):
            artElems = self.artifactElements(pg)
            for artifactElems in artElems:
                # First element is the artifact element
                artifact, artype = artifactElems[0]
                
                # Skip this
                if (len(artifact) < 3): continue
                artifactDict = artifact[1]
                
                # This has to be a property dictionary
                try:
                    atype = artifactDict['/Type']
                    # If atype is pagination look for /Subtype
                    if (atype == '/Pagination'):
                        if '/Subtype' in artifactDict:
                            subtype = artifactDict['/Subtype']
                            key = '.'.join((str(pg+1),subtype))
                            # Bug: text apparently could also be part of
                            # the '/Contents' element here.
                            # File: bugs/wcag.14/testdokument.pdf
                            if '/Contents' in artifactDict:
                                text = artifactDict['/Contents']
                            else:
                                text = self.getArtifactContent(artifactElems)
                            # print 'TEXT:',text
                            # For header simply check it is a non-empty
                            # string. For footer, check if the page number
                            # is part of the string. No need of stricter
                            # checking (against page section headers etc)
                            # for the time being, since most PDF documents
                            # don't implement even the basic Artifact
                            # property list for this test anyway!

                            # Bug: Sometimes the /Footer data is presented as
                            # part of '/Header' subtype. E.g: bugs/wcag.14/testdokument.pdf
                            # So we need to account for it. hence using defaultdict here.
                            if subtype == '/Header':
                                if text:
                                    # Sometimes '/Header' is used for '/Footer' also
                                    if key in pgKeys:
                                        # Use '/Footer' key
                                        key = '.'.join((str(pg+1),'/Footer'))
                                    pgKeys[key] = 1
                            elif (subtype == '/Footer'):
                                # pgstr1 = '%d ' % (pg+1)
                                # pgstr2 = ' %d' % (pg+1)
                                # pgstr3 = ' %d ' % (pg+1)                            
                                # if text.startswith(pgstr1) or \
                                #    text.endswith(pgstr2) or \
                                #    (pgstr3 in text):
                                if text:
                                    # Reverse swap - not much chance of this, but just in case.
                                    if key in pgKeys:
                                        # Use '/Header' key
                                        key = '.'.join((str(pg+1),'/Header'))                                   
                                    pgKeys[key] = 1
                        else:
                            # Some PDF files dont seem to define this key
                            # In that case, check whether the /Attached keys
                            # are defined. If so both Top and Bottom should
                            # be defined. For example, the test file
                            # tests/kommune/hole/Budsjettdokument-\ horingsutkast\ oppdatert\ av\ Per2.pdf
                            # don't define Subtypes but still shows running
                            # headers/footers correctly.
                            try:
                                attKey = artifactDict['/Attached']
                                if type(attKey) in (list, generic.ArrayObject):
                                    val = attKey[0]
                                else:
                                    val = attKey
                                pgKeys['.'.join((str(pg+1),val))] = 1
                            except KeyError:
                                pass
                                    
                except KeyError:
                    pass


        # print pgKeys
        # if there is only one page we don't expect it
        # to have a running header-footer, so it is by
        # default a case where the test can be said as not
        # applicable. If a single page PDF provides a running
        # header-footer it is pretty good :)
        if len(self.pages) == 1 and len(pgKeys) == 0:
            # Not applicable
            return 2

        # print 'PAGEKEYS:',pgKeys
        failed = 0
        # First page is typically an introduction
        # page or a heading page or a TOC page
        # etc, so skip it anyway 
        for pgnum in range(1, len(self.pages)):
            pgid = str(pgnum+1)
            
            try:
                # Check for header and footer keys
                pgKeys['.'.join((pgid, '/Header'))]
                pgKeys['.'.join((pgid, '/Footer'))]
                self.updateResult(results[1], pgnum+1)                                                    
            except KeyError:
                # If this fails check for /Top and /Bottom keys
                try:
                     pgKeys['.'.join((pgid, '/Top'))]
                     pgKeys['.'.join((pgid, '/Bottom'))]
                     self.updateResult(results[1], pgnum+1)
                except KeyError:
                    failed += 1
                    self.updateResult(results[0], pgnum+1)                                    

        # Need to define debug levels for printing
        # output rather than using 'print' - LATER.
        # print 'PAGINATION:',results
        
        # If all pages failed, return a single error
        # for entire document. Checking against numPages -1
        # cuz we are skipping first page.
        if (failed == (len(self.pages) - 1)):
            return 0
        
        return results

    def test_WCAG_PDF_03(self):
        """ This test checks consistent tab and reading
        order for PDF documents. This is test #3 in
        WCAG 2.0 """

        # For the time being, for tagged documents
        # also this is a pass - till we split
        # this test further.
        if self.structroot != None:
            # No need to check '/Tabs'
            return 1
        
        # In tests with PAC checker and verification
        # with wampy tool, it has been found that
        # checking whether '/Tabs' exist for each
        # page and verifying if it equals '/S' is
        # enough to pass this test.

        count = 0
        
        for p in range(len(self.pages)):
            try:
                pg = self.getPage(p)
                tab = pg['/Tabs']
                if tab == '/S':
                    count += 1
            except KeyError:
                pass


        if count == len(self.pages):
            # Passed
            return 1

        # Failed
        return 0

        
    test_WCAG2_BgImages = test_WCAG_PDF_04
    test_WCAG2_AccessibleTables = test_WCAG_PDF_06
    test_WCAG2_FormFieldsNameRoleValue = test_WCAG_PDF_12
    test_WCAG2_FormSubmitButton = test_WCAG_PDF_15
    test_WCAG2_ConsistentPageNumbering = test_WCAG_PDF_17
    test_WCAG2_LinksTextAndLinksAlt = test_WCAG_PDF_11_13
    
