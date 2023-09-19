import re
import collections
import pdfstruct
import logging
import config
import helper

from PyPDF2.generic import *
from PyPDF2.filters import *
from pdfAWAMHandler import PdfAWAMHandler

class PdfStructureError(Exception):
    pass

class PdfWCAG(pdfstruct.PdfStruct):
    """ This class implements those PDF tests and techniques
    as advocated by WCAG 2.0. It is derived from PdfStructureMixin
    so as to inherit the already existing PDF-WAM behaviour """

    # PDF version is righ at the beginning
    # it has to be a string like '%PDF-<major>.<minor>'
    version_re = re.compile(r'\%PDF-\d+\.\d+', re.IGNORECASE)
    # Header types
    header_re = re.compile(r'/h[1-9]',re.IGNORECASE)
    # Parsed form field element types
    # (from WCAG 2.0 techniques)
    form_elems = ('/Tx','/Btn','/Ch','/Sig')
    
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

    is_scanned = property(lambda self: self.get_is_scanned(), None, None)
    struct_tree = property(lambda self:self.get_structure_tree(), None, None)
    font = property(lambda self: self.get_font_resource(), None, None)
    num_images = property(lambda self: self.get_num_images(), None, None)
    
    def __init__(self, verbose=True, stream=None):
        self.stream = stream
        self.version = ''
        self.creator = ''
        self.producer = ''
        self.author = ''
        self.subject = ''
        self.title = ''
        # Root object
        self.root = None
        # Numbers tree
        self.numstree = {}
        # Structure tree root
        self.structroot = None
        # Page number where error is seen
        self.page = 0
        # List of producers which produce scanned PDF
        self.scproducers = ["Adobe PDF Scan Library",
                            "KONICA MINOLTA bizhub C253",
                            "Hewlett-Packard Intelligent Scanning Technology",
                            "Canon iR C2880"]

        # dictionary of processed AWAM IDs here
        # this helps to make the code more readable
        self.awamids = {'wcag.pdf.18': 'EIAO.A.15.1.1.4.PDF.1.1',
                        'wcag.pdf.16': 'EIAO.A.10.4.1.4.PDF.1.1',
                        'egovmon.pdf.05': 'EIAO.A.10.8.1.4.PDF.1.1',
                        'egovmon.pdf.08': 'EIAO.A.10.3.1.4.PDF.1.1',
                        'wcag.pdf.09': 'EIAO.A.10.3.5.4.PDF.1.1',
                        'wcag.pdf.02': 'EIAO.A.10.13.3.4.PDF.1.1',
                        'egovmon.pdf.03': 'EIAO.A.10.3.2.4.PDF.1.1'
                        }

        self.n_artifact_imgs = 0
        self.memo = {}
        self.verbose = verbose
        # Logger
        self.logger = logging.getLogger('pdfwam')        
        # Read the PDF for signature
        # self.read(self.stream)
        
    def read(self, stream):
        """ Read the PDF file """

        # Rewind stream to beginning
        stream.seek(0)
        # This just reads the PDF version
        # Rest is handled by pyPdf.
        s = stream.read(8).decode("utf-8")
        if not self.version_re.match(s):
            self.logger.error("PdfStructureError: Missing PDF version marker!")
            raise PdfStructureError('Error - missing PDF version marker!')

        self.version = s.replace('%PDF-','')
        
    def fill_info(self):
        """ Fill metadata information for the document """
        
        # This is called after PDF parsing is done
        # by pyPdf. So fill in document info from
        # Info marker.
        metadata = self.metadata
        self.logger.info("Getting document metainfo...")
        # Should be called after any decryption of the PDF
        self.creator = metadata.get("/Creator", '')
        self.producer = metadata.get("/Producer", '')
        self.author = metadata.get("/Author", '')
        self.title = metadata.get("/Title", '')
        self.subject = metadata.get("/Subject", '')
        self.ctime = metadata.get("/CreationDate", '')
        self.mtime = metadata.get("/ModDate", '')

        # Fix indirect objects if any.
        for field in ('creator','producer','author','title','subject'):
            val = getattr(self, field)
            if type(val) == IndirectObject:
                try:
                    actual_val = str(val.get_object())
                    setattr(self, field, actual_val)
                except Exception as e:
                    self.logger.error('Error getting object from IndirectObject for property',field,'...')
                    self.logger.error('\tError is',e)

    def encode_ascii(self, val):
        """ Encode string in ASCII and return """


        try:
            if type(val) == IndirectObject:
                val = str(val.get_object())

            val_a = str(val, 'ascii', 'ignore').encode()
        except TypeError:
            val_a = val.encode('ascii', 'ignore')

        return val_a

    def assign_mwam_ids(self):
        """ Assign MWAM PDF property IDs """

        self.logger.info("Assigning MWAM ids")

        attrs = ('title','author','version','ctime','mtime','producer','creator')
        vals = [getattr(self, x) for x in attrs]
        items = list(map(self.encode_ascii, vals))
        self.logger.debug("MWAM properties =>", items)

        # Title MWAM
        self.awamHandler.resultMap['EGOVMON.PDF.PROP.01'] = {(0, 1): items[0].decode()}
        # Author MWAM
        self.awamHandler.resultMap['EGOVMON.PDF.PROP.02'] = {(0, 1): items[1].decode()}
        # Version MWAM
        self.awamHandler.resultMap['EGOVMON.PDF.PROP.03'] = {(0, 1): items[2].decode()}
        # Creation time MWAM
        self.awamHandler.resultMap['EGOVMON.PDF.PROP.04'] = {(0, 1): items[3].decode()}
        # Modification time MWAM
        self.awamHandler.resultMap['EGOVMON.PDF.PROP.05'] = {(0, 1): items[4].decode()}
        # Producer MWAM
        self.awamHandler.resultMap['EGOVMON.PDF.PROP.06'] = {(0, 1): items[5].decode()}
        # Creator MWAM
        self.awamHandler.resultMap['EGOVMON.PDF.PROP.07'] = {(0, 1): items[6].decode()}

    def init(self):
        """ Initialize objects required for processing """

        self.logger.info("Initializing AWAM")

        # Make the nums tree
        self.build_numbers_tree()

        try:
            roleMap=self.structroot['/RoleMap'].get_object()
        except (KeyError, ValueError, AssertionError) as e:
            roleMap=None
        except Exception as e:
            roleMap=None

        # Fill in the meta AWAM ids
        # awamHandler is the object
        self.awamHandler=PdfAWAMHandler(roleMap=roleMap,debug=0,
                                        validateImages=int(config.pdfwamvalidateimgs),
                                        ignoreSingleBitImgs=int(config.pdfwamignoresinglebitimgs))
        # awam_handler is the function!
        self.awam_handler=self.awamHandler.handler

        # Initialize all AWAM IDs
        for awamid in list(self.awamids.values()):
            self.awamHandler.resultMap[awamid] = {(0,1): 0}

    def set_awam_id(self, name, value=1, page=0):
        """ Set the value for the AWAM ID matching the given test """

        self.awamHandler.resultMap[self.awamids.get(name)] = {(page,1): value}
        self.memo[name] = value

    def process_awam(self):
        """ Fill the AWAM dictionary with information for each
        supported WAM identifier, including the structure tree """

        self.assign_mwam_ids()

        # Some AWAMs are processed right here. These are,

        # Title AWAM - WCAG.PDF.18
        self.set_awam_id('wcag.pdf.18', int(len(self.title)>0))
        # Lang AWAM - WCAG.PDF.16
        # Some documents define language in the root object as '/Lang' attribute
        try:
            lang = self.root['/Lang']
            self.set_awam_id('wcag.pdf.16', 1)
            self.awamHandler.resultMap['EIAO.A.0.0.0.0.4.PDF.4.1'] = lang
            # Set langcheck flag
            self.awamHandler.langcheck = True
        except:
            self.set_awam_id('wcag.pdf.16', 0)

        # Encryption AWAM -> EGOVMON.PDF.05
        encrypted = '/Encrypt' in self.trailer
        if not encrypted:
            self.set_awam_id('egovmon.pdf.05', 1)
        else:
            # Get encrytption dictionary
            encd = self.trailer['/Encrypt']
            # Get /R value
            revision = encd.get('/R',2)
            permissions = helper.int2bin(encd.get('/P',1))
            bit5, bit10 = int(permissions[-5]), int(permissions[-10])
            # For revision 2, we check only bit5
            if revision==2:
                self.set_awam_id('egovmon.pdf.05', bit5)
            # For revision>=3,we do an OR
            elif revision>=3:
                self.set_awam_id('egovmon.pdf.05', bit5|bit10)

        # Scanned PDF AWAM -> EGOVMON.PDF.08
        self.set_awam_id('egovmon.pdf.08', int(not self.get_is_scanned()))

        # Consistent headers AWAM -> WCAG.PDF.09
        if (self.structroot != None) and (len(self.structroot) > 0):
            flag = self.document_headers_consistent()
            if flag:
                self.set_awam_id('wcag.pdf.09', 1)
            else:
                # Adding page number where this failed
                self.set_awam_id('wcag.pdf.09', 0, self.page)
        else:
            # We need to remove the entry from results since
            # we pre-initialize everything now
            del self.awamHandler.resultMap[self.awamids.get('wcag.pdf.09')]
            self.logger.info('Document header check not applicable because struct-tree is absent')

        # Bookmarks AWAM -> WCAG.PDF.02
        self.set_awam_id('wcag.pdf.02', int(self.has_bookmarks()))

        # Structure tags AWAM -> EGOVMON.PDF.03
        if self.structroot==None:
            self.set_awam_id('egovmon.pdf.03', 0)
            return
        else:
            # For the time being, we are setting this entry to pass even
            # if the structure tree root object cannot be accessed by pyPdf
            # (example: for the document tests/fw208_accessible.pdf)
            self.set_awam_id('egovmon.pdf.03', 1)

        # If structroot is None or empty return
        if (self.structroot==None) or (len(self.structroot)==0):
            self.logger.warning("Empty structure tree root")
            return

        try:
            # Search the /K kids of the structure tree root
            if type(self.structroot['/K']) is list:
                self.search(self.structroot['/K'])
            else:
                self.search(self.structroot['/K'].get_object())
        except KeyError as ex:
            self.logger.error('Error getting key "/K" from struct root:', ex)

        # Update the memo with WCAG.PDF.01 result
        handler = self.awamHandler
        nimgs = len(handler.figureEls)

        if nimgs>0:
            # Some images are present so wcag.pdf.01 is applicable
            nfimgs = len(handler.failedImgs)
            self.memo['wcag.pdf.01'] = (nfimgs, nimgs - nfimgs)

    def awam_dispatcher(self, item):
        """ Dispatch function calls to AWAM handler """

        if type(item) in (NameObject, NumberObject):
            self.awam_handler(item)
        elif type(item) in (dict, DictionaryObject, IndirectObject):
            try:
                if type(item['/S']) is IndirectObject:
                    self.search(item['/S'])
                else:
                    self.awam_handler(item)
                    # Ticket #125: Need to search recursively
                    # into the Kids of this object, if any
                    try:
                        item_kids = item['/K']
                        for k in item_kids:
                            try:
                                # This is important since a Kid might
                                # be a number object, so it can cause
                                # an exception and then control may
                                # not pass on to next kid ! - this
                                # caused a bug in wrong reporting of
                                # link annotation test failure for OO
                                # exported PDF documents.
                                self.search(k.get_object())
                            except:
                                pass
                    except:
                        pass

            except KeyError as e:
                # FIXME: Check if this always should be pass
                pass
        else:
            self.logger.error("PdfStructureError: invalid type of item",type(item))
            raise PdfStructureError

        return

    def search(self, tree):
        """ Traverse the PDF structure tree which is a PDF number tree """

        # Print all items within the branch
        if type(tree) in (NameObject, NumberObject):
            return

        if type(tree) in (IndirectObject, dict, DictionaryObject):
            self.awam_dispatcher(tree)
            # Try to search kids of this tree
            try:
                self.search(tree['/K'])
            except KeyError as e:
                pass

        elif type(tree) in (list, ArrayObject):
            for item in tree:
                item_obj = item.get_object()
                self.awam_dispatcher(item_obj)

                try:
                    l = item_obj['/K']
                except KeyError:
                    # Item has no kids.
                    continue
                except TypeError:
                    # An object that is unsubscriptable
                    # like a NumberObject
                    continue
                    

                # Ticket #125: Need to check for type ArrayObject
                # also, otherwise we might skip Kids of this
                # object
                if type(l) not in (list, ArrayObject):
                    l = [l]

                for kid in l:
                    kid = kid.get_object()

                    if type(kid) is IndirectObject:
                        self.awam_dispatcher(kid)
                    elif type(kid) in (dict, DictionaryObject):
                        self.awam_dispatcher(kid)
                    elif type(kid) is (int, NumberObject):
                        self.awam_dispatcher(self.numstree[kid])
        else:
            self.logger.error("PdfStructureError: invalid type of item", type(tree))
            raise PdfStructureError

        return

    def document_headers_consistent(self):
        """ Return whether the document uses headers consistently.
        This returns True if document has no headers at all """

        # Load all pages info
        try:
            if len(self.outline)==0:
                self.logger.warning('Warning: document has no headers!')
                # No headers in document
                return True
        except Exception as ex:
            self.logger.error('Error accessing self.outline attribute - ', ex)
            # return True

        # Load all pages info
        # Flatten page dictionary
        self._flatten()
        pgs = self.flattened_pages

        # Numbers dictionary, get all header types from it
        vals = [v.get_object() for v in list(self.numstree.values())]

        headers = {}
        for count in range(len(self.pages)):
            headers[count+1] = []

        for v in vals:
            items = [item.get_object() for item in v]
            for item in items:
                try:
                    if self.header_re.match(item['/S']):
                        # Get page to which the item belongs
                        try:
                            item_pg = item['/Pg']
                        except KeyError:
                            print('No /Pg key found, checking inside /K')
                            item_pg = item['/K']['/Pg']
                        # Get page number
                        try:
                            pgnum = pgs.index(item_pg) + 1
                            headers[pgnum].append(item)
                        except ValueError:
                            # Page not matching, skip this
                            pass

                except TypeError as e:
                    pass

        # The first header if any should be H1, otherwise
        # we can return error straight-
        firstpg = 1
        if len(headers):
            # Get first header
            for pgnum in headers:
                if len(headers[pgnum]):
                    # First header
                    firstpg, hdr1 = pgnum, headers[pgnum][0]['/S'].lower()
                    self.logger.debug('First header=>',firstpg, hdr1)
                    if hdr1 != '/h1':
                        self.logger.error('Error: Document starts with header %s(page:%d)' % (hdr1, pgnum))
                        self.page = pgnum
                        return False
                    # Break otherwise
                    break

        # Heading level skip check
        l,lprev,pgprev=0,0,0
        for pgnum in range(firstpg, len(self.pages)+1):
            pghdrs = headers[pgnum]
            # No headers in page, continue
            if len(pghdrs)==0: continue
            try:
                levels = [int(item['/S'].lower().replace('/h','')) for item in pghdrs]
            except ValueError as e:
                print(('Error:',e))
                continue

            for l in levels:
                # Shouldn't jump levels

                if l>lprev:
                    if (l-lprev)>1:
                        # Skipping header level
                        self.logger.error('Error: Header inconsistency in pg %d: level h%d follows h%d (pg:%d)!' % (pgnum, l, lprev, pgprev))
                        self.page = pgnum
                        return False
                elif l<lprev:
                    # Pass
                    pass

                lprev = l
                pgprev = pgnum

        return True

    def run_all(self):
        """ Wrapper method for running all wcag 2.0 tests """

        results = {}

        for name in dir(self):
            if name.startswith('test_WCAG'):
                func = getattr(self, name)
                ret = func()
                results[name] = ret

        return results

    def run_selected_test(self, test_id, results):
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
            
    def run_all_tests(self):
        """ Run all PDF WAM tests """

        self.init()
        self.process_awam()
        results = self.awamHandler.resultMap

        for test_id in self.test_ids:
            self.run_selected_test(test_id, results)

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

    def update_result(self, result, pg, target=None):
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

    def init_result(self):
        return {0: {}, 1: {}}
    
    def document_has_consistent_page_numbers(self):
        """ This tests consistent page numbering across
        PDF page viewer controls and the PDF document.
        This is test #17 in WCAG 2.0 """

        pl = self.get_page_labels()
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

    def document_has_accessible_hyperlinks(self, wamdict):
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

        if not self.has_external_links():
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
        
        for extLink, pg in self.get_external_links():
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

    def document_has_accessible_forms(self):
        """ This test checks whether every form field
        has been assigned the appropriate name/role/value triple.
        This is test #12 of WCAG-2.0 PDF techniques """
        
        # We need to follow the N/R/V table specified in
        # http://www.w3.org/WAI/GL/WCAG20-TECHS/pdf.html#PDF12
        # to the word, for this test. Since each type of
        # form control has different ways of accessing these
        # fields, they have to be coded separately.

        form = self.get_form_object()
        
        # No forms found, test not applicable
        if form is None:
            self.logger.info('No Form object found in Document')
            return 2

        # import pdb;pdb.set_trace()
        types = collections.defaultdict(int)
        for item in self.fetch_form_fields(form):
            try:
                ffield = item.get_object()
                types[ffield['/FT']] += 1
            except:
                pass

        print('All form field types =>', types)
        for item in self.fetch_form_fields(form):
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
                        if type(state) != NumberObject:
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
            
    def document_has_accessible_submit_buttons(self):
        """ Test if a form which submits data has a proper submit button
        with an associated submit action. This is test #15 in PDF-WCAG2.0
        techniques """

        form = self.get_form_object()
        
        # No forms found, test not applicable
        if form==None:
            self.logger.info('No Form object found in Document')
            return 2

        pushbtns = []
        
        for item in self.fetch_form_fields(form):
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

    def document_has_accessible_tables(self):
        """ Test if the tables (if any) defined in the PDF
        document are accessible. This is test #6 in PDF-WCAG2.0
        techniques """

        if len(self.awamHandler.tableStructDict) == 0:
            self.logger.info('No tables found in Document')
            # No tables ? test not applicable
            return 2

        results = self.init_result()
        self.logger.debug('No of tables =>',len(self.awamHandler.tableStructDict))

        # Loop through each and see if it is marked invalid
        #if any([x.invalid for x in self.awamHandler.tableStructDict.values()]):
        #    # Failed
        #    print 'Invalid table structure found in Document'            
        #    return 0
        # import pdb; pdb.set_trace()
        for tbl in list(self.awamHandler.tableStructDict.values()):
            pg = tbl.get_page()
            if tbl.invalid:
                # import pdb; pdb.set_trace()
                self.update_result(results[0], pg, tbl)
            else:
                self.update_result(results[1], pg, tbl)
                
        self.logger.info('wcag.pdf.06 - Test completed')
        return results

    def document_bg_images_accessible(self):
        """ Test if any background image is specified correctly.
        This is test #4 in PDF WCAG 2.0 techniques """

        # Since we have no way of knowing if an image
        # is decorative by inspecting the structure/content,
        # this test does some basic checks on /Artifact
        # type elements which could be images and verifies
        # if they are specified correctly.

        imgRe = re.compile(r'(\/Im\d+)|(\/Fm\d+)')
        imgArtifacts = 0

        results = self.init_result()
        
        for pg in range(len(self.pages)):
            for artifactElems in self.artifact_elements(pg):
                # First element is the artifact element
                artifact, artype = artifactElems[0]
                if artype=='BMC':
                    # artifact should be like ['/Artifact']
                    if len(artifact) != 1:
                        # Error
                        self.logger.debug('/Artifact type is BMC, however artifact element',artifact,'has invalid length!')
                        self.update_result(results[0], pg+1, artifact)
                elif artype=='BDC':
                    # artifact should be like ['/Artifact', {}]
                    if len(artifact) != 2:
                        # Error
                        self.logger.debug('/Artifact type is BMC, however artifact element',artifact,'has invalid length!')
                        self.update_result(results[0], pg+1, artifact)                        
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
                    self.update_result(results[1], pg+1)                    

        self.logger.info('Number of img artifacts =>',imgArtifacts)
        self.logger.info("Number of images =>", self.get_num_images())
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
        
        
        results = self.init_result()
        pgKeys = {}
        
        for pg in range(len(self.pages)):
            artElems = self.artifact_elements(pg)
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
                                if type(attKey) in (list, ArrayObject):
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
                self.update_result(results[1], pgnum+1)                                                    
            except KeyError:
                # If this fails check for /Top and /Bottom keys
                try:
                     pgKeys['.'.join((pgid, '/Top'))]
                     pgKeys['.'.join((pgid, '/Bottom'))]
                     self.update_result(results[1], pgnum+1)
                except KeyError:
                    failed += 1
                    self.update_result(results[0], pgnum+1)                                    

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
                pg = self.pages[p]
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

    def get_json(self):
        """ Return test results as a dictionary """
        
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
       

    # Aliases
    test_WCAG_PDF_17 = document_has_consistent_page_numbers
    test_WCAG_PDF_04 = document_bg_images_accessible
    test_WCAG_PDF_06 = document_has_accessible_tables
    test_WCAG_PDF_12 = document_has_accessible_forms
    test_WCAG_PDF_15 = document_has_accessible_submit_buttons
    test_WCAG_PDF_11_13 = document_has_accessible_hyperlinks
    
