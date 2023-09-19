import re
import config
import random
import logging

from PyPDF2.generic import *
from PyPDF2.filters import *
from pdfAWAMHandler import PdfAWAMHandler

pdf_version_re = re.compile('PDF\-\d\.\d$')

def memoize(function):
    """ Memoizing decorator serving as a cache for functions
    whose state is memoized in dictionaries """

    _memoized = {}

    def wrapper(instance, *args):
        # Create a place holder for the instance
        try:
            _memoized[instance]
        except KeyError:
            _memoized[instance] = {}

        # Cache the functions output or return from
        # previously cached data.
        try:
            return _memoized[instance][args]
        except KeyError:
            _memoized[instance][args] = function(instance, *args)
            return _memoized[instance][args]

    return wrapper

def int2bin(n, count=32):
    """ Returns the binary of integer n as string, using count number of digits """

    return "".join([str((n >> y) & 1) for y in range(count-1, -1, -1)])

class PdfStructureError(Exception):
    pass

class PdfStructureMixin(object):
    """ This is intended as a mix-in class for PyPDF to
        provide PDF AWAM handling and evaluation for the EIAO Observatory.
    """

    # PDF version is righ at the beginning
    # it has to be a string like '%PDF-<major>.<minor>'
    version_re = re.compile(r'\%PDF-\d+\.\d+', re.IGNORECASE)
    # Header types
    header_re = re.compile(r'/h[1-9]',re.IGNORECASE)
    # Parsed form field element types
    # (from WCAG 2.0 techniques)
    form_elems = ('/Tx','/Btn','/Ch','/Sig')

    def __init__(self, logger=None):
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

        self.nArtifactImgs = 0
        self.memo = {}
        self.verbose = True
        # Logger
        self.logger = logging.getLogger('pdfwam')

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

    def build_numbers_tree(self):
        """ Make numbers dictionary from structure tree """

        self.numstree = {}

        self.logger.info("Making numbers tree")
        # Structure tree WAMs
        try:
            self.structroot = self.root['/StructTreeRoot'].get_object()
        except (KeyError, ValueError, AssertionError) as e:
            # We are not sure on the struct tree - so allow it to be true
            self.structroot = {}
            # raise
            # If it is a problem with PDF version then it is a pyPdf error
            # so assume StructureTree is fine
            err_msg = str(e).replace("'",'').replace('"','').strip()
            print('Error =>', e.__class__.__name__, err_msg)
            if pdf_version_re.search(err_msg):
                self.logger.error("Problem with PDF version >= 1.7 with pyPdf - Allowing dubiousness in structure tree result (Frontend will show result as PASS)")

            self.logger.error("Error: couldn't get structure tree!")
            # The previous KeyError with wrong structure tree
            # becomes a valueerror after fixIndirectObjectXref is
            # called (for one test PDF), so catch it.
            return
        except Exception as e:
            self.logger.error("Error: couldn't get structure tree!", str(e))
            return

        try:
            parenttree = self.structroot['/ParentTree'].get_object()
        except KeyError as e:
            self.logger.error("Error: couldn't get parent tree!")
            return

        # Convert the PDF number tree to a Python dictionary to make it
        # easier to process.

        nums_found = False

        try:
            keys=parenttree['/Nums'][0::2]
            values=parenttree['/Nums'][1::2]
            nums_found = True
        except KeyError:
            keys=[]
            values=[]

        # Try children of parent tree
        if not nums_found:
            nums = []
            try:
                for kid in parenttree['/Kids']:
                    kid = kid.get_object()
                    num = kid['/Nums']
                    nums += num
            except KeyError:
                pass

            keys=nums[0::2]
            values=nums[1::2]

        for i in range(0,len(keys)):
            self.numstree[keys[i]]=values[i]

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
            permissions = int2bin(encd.get('/P',1))
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

    def fix_indirect_object_xref(self):
        """ Fix indirect cross object references """

        self.logger.info("Fixing indirect object X references")

        xref = self.xref

        root_idnums = []
        for item in list(self.root.values()):
            if type(item) is IndirectObject:
                root_idnums.append(item.idnum)
            else:
                root_idnums.append(-1)

        wrongids = []
        gens = []
        # Fix the indirect object generations by
        # cross checking with the xref dictionary
        for generation in list(xref.keys()):
            idrefs = xref[generation]
            gens.append(generation)

            for idnum, val in list(idrefs.items()):
                # Check if this object exists in root dictionary
                if idnum in root_idnums:
                    idx = root_idnums.index(idnum)
                    obj = list(self.root.values())[idx]
                    # Fix generation, if mismatch
                    if obj.generation != generation:
                        wrongids.append([idnum, generation, obj.generation])

        self.xref2 = {}
        for g in gens:
            self.xref2[g] = {}

        for idnum, oldgen, gen in wrongids:
            idref = xref[oldgen]
            ref = idref[idnum]
            xref[gen][idnum] = ref
            del idref[idnum]

    def content_stream(self, pgnum):
        """ Given a page number, return its content stream """

        p = self.pages[pgnum]
        content = p['/Contents'].get_object()
        if not isinstance(content, ContentStream):
            try:
                content = ContentStream(content, self)
            except Exception as e:
                self.logger.error('Error while creating content stream for page %d: [%s]' % (pgnum, str(e)))
                return None

        return content

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

    def has_bookmarks(self):
        """ Return whether the PDF document has bookmarks """

        try:
            outlines = self.root['/Outlines'].get_object()
            # no of bookmarks
            count = int(outlines.get('/Count', 0))
            # first bookmark
            first = outlines['/First'].get_object()
            # last bookmark
            last = outlines['/Last'].get_object()

            # Bookmarks present if either count>0 or
            # if we find that both first and last items
            # not None
            if (count>0) or ((first != None) and (last != None)):
                return True
            else:
                return False
        except KeyError:
            return False
        except ValueError as e:
            print('Unexpected error in checking bookmarks=>', e)
            return False
        
    def _has_columns(self, pgnum):
        """ Return whether a given page has text in more than
        one column """

        # The logic is highly improved from the previous one
        # and this implementation can even differentiate between
        # pages with tables and pages with text actually
        # in wide columns! It doesn't flag pages with small
        # tables wrongly as multi columned which the previous
        # one did.

        pg = self.pages[pgnum]
        try:
            cropbox = pg['/CropBox']
            cropY = float(cropbox[3])
            cropX = float(cropbox[2])
        except:
            return False

        text = pg.extractText()
        if text == '':
            # Don't bother with pages containing no text
            return False

        conts = self.content_stream(pgnum)
        if conts != None:
            # If operand is a 6 member integer list it indicates
            # the pixel/dimension extents of the box in which the
            # data is to be painted. Something like
            # [12, 0, 0, 12, 90, 692] i.e [f, x1, y1, f, x2, y2]
            # where (x1, y1) is the left extent of the text and
            # (x2, y2) the right extent measured from the top-most
            # left corner being (0,0). The key point is that if
            # the text is multi-column then x2 changes across a
            # page, otherwise x2 will be same. The operator
            # is either 'Tm', 'cm' etc.
            text_extents = []
            for x,y in conts.operations:
                if type(x) is list and len(x)==6:
                    text_extents.append(([float(item) for item in x], y))

            if len(text_extents):
                x2_0, y2_0 = text_extents[0][0][4:]
                op = text_extents[0][1]
                # If <0, then skip
                if ((x2_0<0) and (y2_0<0)):
                    return False

                # If zeroes, make them 1s
                # if x2_0==0: x2_0 = 1
                if y2_0==0: y2_0 =1

                x2_prev, y2_prev = 0, 0

                count, l = 0, len(text_extents)
                for item, op in text_extents:
                    # if count==0: continue
                    # check x2
                    x2,y2 = item[4:]
                    if x2<x2_0:
                        # Typically indicates a table
                        break
                    # Y should be at least twice as much as yprev
                    # and at least 80% of the cropbox Y
                    elif (x2>x2_0) and (y2>=2*y2_prev) and (y2>=0.70*cropY):
                        self.logger.debug('Pg #%d - Column change: (%d,%d) to (%d,%d): %s' % (pgnum+1, x2_prev,y2_prev,x2,y2, op))
                        # Surely indicates move of text to another column
                        return True

                    x2_prev, y2_prev = x2,y2
                    count += 1

        return False

    def document_has_columns(self):
        """ Find out if the document has multiple columns """

        # Check all pages
        pgs = []
        for pgnum in range(0, len(self.pages)):
            if self._has_columns(pgnum):
                pgs.append(str(pgnum+1))

        if len(pgs):
            self.logger.info('These pages have multiple columns: %s' % ','.join(pgs))
            return True

        return False

    def _has_multimedia(self, pgnum):
        """ Find out if a given page has embedded or
        linked multi-media (video/audio) content """

        pg = self.pages[pgnum]
        # If there is no '/Annots' key, return False
        try:
            annots = pg['/Annots']
        except KeyError:
            return False

        if annots is None:
            return False

        # Check if annotation is Movie, Sound or Screen types
        for anot in annots:
            anot = anot.get_object()
            # Also for the time being assuming FileAttachments are multimedia types
            if anot['/Subtype'] in ('/Movie','/Sound','/Screen', '/FileAttachment'):
                return True
            # Check for contents...

        return False

    def _has_embedded_multimedia(self, pgnum):
        """ Find out if a given page has embedded multimedia """

        pg = self.pages[pgnum]
        # If there is no '/Annots' key, return False
        try:
            annots = pg['/Annots']
        except KeyError:
            return False

        if annots is None:
            return False

        # Check if annotation is Movie, Sound or Screen types
        for anot in annots:
            anot = anot.get_object()
            if anot['/Subtype'] == '/FileAttachment':
                return True
            elif anot['/Subtype'] in ('/Movie','/Sound','/Screen'):
                # See if this is a URI
                try:
                    elem = anot[anot['/Subtype']]
                    elem_f = elem['/F']
                    elem_fs = elem_f['/FS']
                    if elem_fs == '/URI':
                        return False
                except KeyError:
                    continue

        return False

    def get_external_links(self):
        """ Retrieve all '/Link' objects of the
        PDF document as a generator """

        for pgnum in range(len(self.pages)):
            pg = self.pages[pgnum]
            try:
                annots = pg['/Annots']
                if annots==None: continue
            except KeyError:
                continue

            for anot in annots:
                anot = anot.get_object()

                if anot['/Subtype'] in ('/Link') or '/URI' in anot:
                    yield (anot, pg)

    def _has_external_links(self, pgnum):
        """ Return whether the page has external links
        (URIs, URLs, email addresses) etc """

        pg = self.pages[pgnum]
        # If there is no '/Annots' key, return False
        try:
            annots = pg['/Annots']
        except KeyError:
            return False

        if annots is None:
            return False

        # Check Muif annotation is Movie, Sound or Screen types
        for anot in annots:
            try:
                anot = anot.get_object()
                # Also for the time being assuming FileAttachments are multimedia types
                if anot['/Subtype'] in ('/Link') or '/URI' in anot:
                    return True
            except ValueError as e:
                print('Unexpected error when fetching annotation object =>',e)
                
            # Check for contents...

        return False

    def has_external_links(self):
        """ Find out if the PDF document contains links (URIs)
        to external objects """

        for pgnum in range(0, len(self.pages)):
            if self._has_external_links(pgnum):
                return True

        return False

    def has_multimedia(self):
        """ Find out if the PDF document contains or refers
        to multimedia """

        for pgnum in range(0, len(self.pages)):
            if self._has_multimedia(pgnum):
                return True

        return False

    def has_embedded_multimedia(self):
        """ Find out if the PDF document contains an
        embedded multimedia file or attachment """

        for pgnum in range(0, len(self.pages)):
            if self._has_embedded_multimedia(pgnum):
                return True

        return False

    def get_is_tagged(self):
        """ Find out whether the PDF document has tag
        marks or not """

        if '/MarkInfo' not in self.root:
            return False

        markinfo = self.root['/MarkInfo'].get('/Marked', {})
        if markinfo:
            return markinfo.value

        return False

    def has_font(self):
        """ Returns if the document resources structure
        has a '/Font' key """

        try:
            res0 = self.get_resource_tree()
            x = res0['/Font']
            return True
        except KeyError:
            return False

    def has_forms(self):
        """ Return whether the PDF document has an interactive
        form """
 
        return '/AcroForm' in self.root

    def has_valid_forms(self):
        """ Return whether the PDF document has a valid form object """

        try:
            form = self.root['/AcroForm']
            # Contains at least 1 field
            return (self.get_num_formfields(form)>0)
        except KeyError:
            return False

    def get_num_formfields(self, form):
        """ Return number of fields in the given form object """

        try:
            fields = form['/Fields']
        except KeyError:
            return 0

        num_fields = 0
        for f in fields:
            field = f.get_object()
            if '/Kids' in field:
                # Compound field
                num_fields += len(field['/Kids'])
            else:
                num_fields += 1

        return num_fields

    def fetch_form_fields(self, form):
        """ Returns an iterator (generator) over
        all the elements of the given form object """

        try:
            fields = form['/Fields']
        except KeyError:
            yield None

        # It is a tricky business to get a recursive
        # generator into a flat iterator! You need
        # two for loops - one outer and one in the
        # recursive generator as well!
        for f in fields:
            for item in self._fetch_form_fields(f):
                yield item

    def _fetch_form_fields(self, f):

        field = f.get_object()
        # First yield field itself
        yield f

        # If field has Kids, process them as well
        try:
            kids = field['/Kids']
            for k in kids:
                kid = k.get_object()
                for item in self._fetch_form_fields(k):
                    yield item

        except KeyError:
            pass

    def has_text_input_form(self):
        """ Return whether the PDF document contains a form
        object with text input fields """

        try:
            form = self.root['/AcroForm'].get_object()
        except KeyError:
            return False

        try:
            for f in form['/Fields']:
                field = f.get_object()
                # Found one text field
                try:
                    if field['/FT']=='/Tx':
                        return True
                except KeyError:
                    # Check if this is a compound form
                    # with children
                    if '/Kids' in field:
                        kids = field['/Kids']
                        for k in kids:
                            kid = k.get_object()
                            try:
                                if kid['/FT']=='/Tx':
                                    return True
                            except KeyError:
                                pass
        except KeyError:
            pass

        return False

    def has_embedded_fonts(self):
        """ Return whether the document has any embedded fonts """

        fonts = self.font
        if fonts == None:
            return False

        embedded = []
        for v in list(fonts.values()):
            f = v.get_object()
            # Check this or "descendant font"
            if '/FontDescriptor' in f:
                fd = f['/FontDescriptor'].get_object()
                if fd==None: continue

                for key in list(fd.keys()):
                    # Embedded fonts will have the '/FontFile*' attribute
                    if key.startswith('/FontFile'):
                        return True

            elif '/DescendantFonts' in f:
                fd=f['/DescendantFonts'][0].get_object()
                if '/FontDescriptor' in fd:
                    fdd = fd['/FontDescriptor'].get_object()
                    if fdd==None: continue

                    for key in list(fdd.keys()):
                        if key.startswith('/FontFile'):
                            return True

        return False

    def get_embedded_fonts(self):
        """ Return a list of embedded font objects in the PDF document """

        fonts = self.font

        embedded = []
        for v in list(fonts.values()):
            f = v.get_object()
            # Check this or "descendant font"
            if '/FontDescriptor' in f:
                fd = f['/FontDescriptor'].get_object()
                if fd==None: continue

                for key in list(fd.keys()):
                    # Embedded fonts will have the '/FontFile*' attribute
                    if key.startswith('/FontFile'):
                        embedded.append(f)
            elif '/DescendantFonts' in f:
                fd=f['/DescendantFonts'][0].get_object()
                if '/FontDescriptor' in fd:
                    fdd = fd['/FontDescriptor'].get_object()
                    if fdd==None: continue

                    for key in list(fdd.keys()):
                        if key.startswith('/FontFile'):
                            embedded.append(f)

        return embedded

    def get_form_object(self):
        """ Return the form object embedded in the document, if any """

        try:
            return self.root['/AcroForm'].get_object()
        except KeyError:
            pass
        except ValueError as e:
            print('Unexpected error when fetching /AcroForm =>',e)

    def get_font_resource(self, pgnum=0):
        """ Return the /Font resource """

        try:
            res0 = self.get_resource_tree()
            return res0['/Font']
        except:
            pass

    def get_page_labels(self):
        """ Return page labels dictionary """
        
        try:
            return self.root['/PageLabels']
        except:
            pass

    def get_structure_tree(self):
        """ Return root of structure tree """
        
        try:
            return self.root['/StructTreeRoot']
        except (KeyError, ValueError, AssertionError) as e:
            pass

    def get_resource_tree(self, pgnum=0):
        """ Returns the resource tree """

        try:
            # import pdb;pdb.set_trace()
            return self.pages[pgnum]['/Resources']
        except Exception as e:
            self.logger.error("Error getting resource tree", e)

    def resource_iterator(self):
        """ Return an iterator on all unique resource trees """

        # This is an odd-way of creating an iterator
        # but I want to make sure, we don't have duplicates
        all_res = []

        for x in range(len(self.pages)):
            res = self.get_resource_tree(x)
            try:
                all_res.index(res)
            except ValueError:
                all_res.append(res)

        return all_res

    def get_is_scanned(self):
        """ Returns whether the PDF is a scanned document,
        by inspecting the resource structure """

        # Check list of producers first
        if self.producer:
            prodl = [prod.lower() for prod in self.scproducers]
            for prod in prodl:
                if self.producer.lower().startswith(prod):
                    self.logger.info('Scan check: found scan producer!', prod)
                    return True

        # If structure tree is defined, definitely
        # not scanned
        if self.structroot != None:
            return False

        # This more rigorous check added after
        # http://www.eu2005.lu/en/savoir_lux/lux_publications/livre_presidence/grand_duche.pdf
        # returned as a scanned PDF wrongly!
        # Check for upto 3 pages
        pgnum = len(self.pages)
        if pgnum==1:
            return self._get_is_scanned()
        elif pgnum==2:
            # Check pages 1 & 2
            return self._get_is_scanned() and self._get_is_scanned(1)
        elif pgnum>2:
            # Check 1st page and 2 random pages
            pg1 = random.randrange(0, pgnum)
            pg2 = random.randrange(0, pgnum)
            return self._get_is_scanned() and \
                   self._get_is_scanned(pg1) and \
                   self._get_is_scanned(pg2)

    def _get_is_scanned(self, pgnum=0):
        """ Return whether document is scanned w.r.t the given page """

        # Check presence of '/Font' resource
        res = self.get_resource_tree(pgnum)
        font= '/Font' in res
        # Make sure the font resource is not empty
        if font:
            font = res['/Font']

        xobj = None
        # See if there is at least one image
        try:
            xobj = res['/XObject']
        except KeyError:
            try:
                xobj = res.get('/XObject')
            except:
                pass

        if xobj==None:
            # No XObject, return False
            return False

        # Not a dictionary ? return False
        if not hasattr(xobj, 'values'):
            return False

        img = xobj and '/Image' in [item.get_object().get('/Subtype') for item in list(xobj.values()) if item]
        # Flag as scanned if font is missing and has at least 1 image
        return (not font) and img

    def image_iterator(self):
        """ An iterator over the images in the current PDF object """

        allimgs = []

        for pgnum in range(len(self.pages)):
            pg = self.pages[pgnum]
            xobj = None

            res = pg['/Resources']

            try:
                xobj = res['/XObject']
            except KeyError:
                try:
                    xobj = res.get('/XObject')
                except:
                    pass

            if xobj is not None and hasattr(xobj, 'values'):
                count = 0
                for item in list(xobj.values()):
                    if item != None and item.get_object().get('/Subtype') in ('/Image'):
                        item = item.get_object()
                        try:
                            allimgs.index(item)
                        except ValueError:
                            allimgs.append(item)
                            count += 1
                            yield item

    def get_num_images(self):
        """ Return number of images in the PDF file """

        count = 0
        for x in self.image_iterator():
            count += 1

        return count

    def get_num_artifact_imags(self):
        """ Return number of images which are artifacts """
        return self.nArtifactImgs

    def get_num_tables(self):
        return len(self.awamHandler.tableStructDict)

    def get_artifact_content(self, artifactElem):
        """ Return the text content inside an artifact element """

        text = ''

        for operands,operator in artifactElem:

            if operator.decode() == "Tj":
                _text = operands[0]
                if isinstance(_text, TextStringObject):
                    text += _text
            elif operator.decode() == "T*":
                text += "\n"
            elif operator.decode() == "'":
                text += "\n"
                _text = operands[0]
                if isinstance(_text, TextStringObject):
                    text += operands[0]
            elif operator.decode() == '"':
                _text = operands[2]
                if isinstance(_text, TextStringObject):
                    text += "\n"
                    text += _text
            elif operator.decode() == "TJ":
                for i in operands[0]:
                    if isinstance(i, TextStringObject):
                        text += i

        return text

    @memoize
    def artifact_elements(self, pgnum):
        """ Return a list of all elements for /Artifact type
        objects in this page """

        # This is one of the costlies functions in terms of CPU
        # time so its return values per page are memoized using
        # a decorator.

        # This returns the complete list of [operands, operations]
        # starting from ['/Artifact'...] ending with ['EMC']
        # as a generator

        cs = self.content_stream(pgnum)
        mark = 0
        artElems = []

        for operands, operator in cs.operations:
            # like (['/Artifact'], 'BMC') or
            # like (['/Artifact', {}], 'BDC')
            # Bug #273 with URL https://www.sor.no/Documents/organisasjon/S%C3%B8r-Pluss-informasjonsdokument-20130529.pdf
            # The operands turns out to be a dictionary so a
            # KeyError results since 0 is not a key
            # Fix - check for type as list.
            if type(operands) != list:
                continue

            if (len(operands)>0 and (operands[0] == '/Artifact')):
                # Eat stuff till you meet an 'EMC' operator
                element = [(operands, operator)]
                mark = 1
            elif ((operator.decode() == 'EMC') and (mark==1)):
                element.append([operands, operator])
                # Reset everything
                mark = 0
                artElems.append(element)
            elif (mark==1):
                element.append([operands, operator])

        return artElems

    def is_lzw_encoded(self):
        """ Return if the document or any image in the
        document is LZW encoded """

        is_lzw = False

        # For each image object try to see if it is
        # LZW encoded
        for i in self.image_iterator():
            f = i.get('/Filter', '')
            if f == 'LZWDecode':
                return True
            elif f=='':
                try:
                    # No filter given, try LZWDecode
                    l=LZWDecode.decode(i.getData())
                    # Decoding success, is lzw encoded
                    return True
                except Exception as e:
                    # Not LZW encoded
                    return False
            else:
                # Some other filter
                pass

        return False

    is_scanned = property(lambda self: self.get_is_scanned(), None, None)
    struct_tree = property(lambda self:self.get_structure_tree(), None, None)
    font = property(lambda self: self.get_font_resource(), None, None)
    num_images = property(lambda self: self.get_num_images(), None, None)
        
