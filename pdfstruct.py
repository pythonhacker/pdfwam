""" Provides class methods to query and perform operations on the PDF object structure """

import re
import helper
import random
from PyPDF2.generic import *
from PyPDF2.filters import *

pdf_version_re = re.compile('PDF\-\d\.\d$')
    
class PdfTblStructInvalidException(Exception):
    pass

class PdfTblStruct(object):
    """ A class to evaluate structural validity of
    PDF tables. Right now only checks for proper
    hierarchy/reading order of elements inside all
    tables in the given PDF document """
    
    # type dict that also acts as a child->parent mapping
    typedict = {'/Table': '',
                '/TR': '/Table',
                '/TH': '/TR',
                '/TD': '/TR'}

    # parent->child mapping dict
    childdict = {'/Table': ('/TR',),
                 '/TR': ('/TH', '/TD'),
                 '/TH': (),
                 '/TD': ()}
                      
    def __init__(self):
        self.init()
        self.current=None

    def init(self, root=None):
        # Current element
        self.current = root
        # Not used
        self.parent=None
        # Previous element
        self.prev=None
        self.level = 0
        # Invalid flag
        self.invalid = 0
        # The page to which this table belongs
        self.page = 0

    def set_page(self, pgnum):
        self.page = pgnum

    def get_page(self):
        return self.page

    def is_page_set(self):
        return (self.page > 0)
    
    def add(self, elem):
        """ Add a table element to the hierarchy """

        # If table is already invalid returns 0. If
        # this element adds incorrect structure, sets
        # invalid flag and raises an Exception. Otherwise
        # returns 1. If the element is the top level
        # element or a duplicate, returns 0 as well.
        
        # Invalid structure, don't do anything
        if self.invalid:
            return 0
        
        # Check hieararchy
        typ = elem['/S']
        # Not a table element ?
        if typ not in list(self.typedict.keys()):
            return 0

        if typ=='/Table':
            self.init(elem)
            return 0

        # Sometimes, same element is called one after
        # another, in that case ignore
        if elem == self.prev:
            return 0

        # Parent type
        parent_type = self.typedict[typ]
        # child type
        child_types = self.childdict[typ]
        save = self.current
        # Set previous to current
        self.prev = save
        # Set current to elem
        self.current = elem
        
        # If previous type is same as parent's type
        # then we are going down one level
        prev_type = self.prev['/S']
        # If prev_type matches parent's type
        # then this is a level down
        if prev_type == parent_type:
            self.level += 1
            self.parent = self.prev
        # Otherwise prev_type can be same
        # as current type
        elif prev_type == typ:
            pass
        # Or prev type can be one type down
        # in which case it is a level up
        elif prev_type in child_types:
            self.level -= 1
        else:
            # import pdb;pdb.set_trace()
            # Invalid structure
            self.invalid = 1
            raise PdfTblStructInvalidException("Error: Invalid table structure!")

        return 1
        
class PdfStruct(object):
    """ Provide structure and methods on the enclosing PDF object """

    # NOTE - This has to be used as a mixin or parent class for
    # a class that inherits from PyPDF2.PdfReader. It does not work
    # on its own.
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
    
    def build_numbers_tree(self):
        """ Make numbers dictionary from structure tree """

        self.numstree = {}

        self.logger.info("Making numbers tree")
        # Structure tree WAMs
        try:
            # import pdb;pdb.set_trace()
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

    def content_stream(self, pgnum):
        """ Given a page number, return its content stream """

        p = self.pages[pgnum]
        content = p['/Contents'].get_object()
        if not isinstance(content, ContentStream):
            try:
                content = ContentStream(content, self)
            except Exception as e:
                self.logger.error('Error while creating content stream for page %d: [%s]' % (pgnum, str(e)))
                return

        return content

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
        return self.n_artifact_imgs

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


    @helper.memoize
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
