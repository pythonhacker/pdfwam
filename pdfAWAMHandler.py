from PyPDF2.generic import IndirectObject, ArrayObject, DictionaryObject

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

    def setPage(self, pgnum):
        self.page = pgnum

    def getPage(self):
        return self.page

    def isPageSet(self):
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
            import pdb;pdb.set_trace()
            # Invalid structure
            self.invalid = 1
            raise PdfTblStructInvalidException("Error: Invalid table structure!")

        return 1
        
class PdfAWAMHandler:
    """
    AWAM handler for PDF structure tree elements.
    """
    def __init__(self, resultMap=None,roleMap=None,validateImages=False,
                 ignoreSingleBitImgs=False,debug=False):
        if resultMap==None:
            self.resultMap={}
        else:
            self.resultMap=resultMap
        self.debug=debug
        # Fake line/column counters.
        # (If necessary, this can be improved in future versions.)
        self.elementCount=0
        self.line=0
        self.roleMap=roleMap
        # Number of form elements with structure
        self.nFormEls = 0
        # Language check already done ?
        self.langcheck = False
        # To make sure we don't add duplicate results
        # for alt-image test
        self.figureEls = []
        # Table accessibility
        self.tableStruct = None
        # Tables evaluated for accessibility
        self.tableStructDict = {}
        # Links evaluated for accessibility
        self.linkAnnots = {}
        # Images without alt text
        self.failedImgs = {}
        # X-Validate alt-image tests with the page element ?
        self.validateImgs = validateImages
        # Ignore single-bit depth images when reporting
        # Alt image test results ?
        self.ignore1bitimgs = ignoreSingleBitImgs
        
    def check(self,element,awamId,dictKey,Pass=None,Fail=1,noAdd=False):
        """
        Add AWAM result to resultmap for PDF documents.
        If dictKey does not exist in element, return fail.
        If pass is None, the dict value is returned. Otherwise the
        pass value is specified.
        """
        try:
            self.resultMap[awamId]
        except KeyError:
            self.resultMap[awamId]={}

        # Add language entry
        try:
            value=element[dictKey]
            if noAdd: return 1
            if Pass == None:
                self.resultMap[awamId][(self.line,self.elementCount)]=element[dictKey]
            else:
                self.resultMap[awamId][(self.line,self.elementCount)]=Pass
            return 1
        except KeyError:
            if noAdd: return 0            
            # dictKey did not exist - indicate barrier.
            if Fail != None:
                self.resultMap[awamId][(self.line,self.elementCount)]=Fail
            return 0

    def getFlattenedPages(self, pgelem):
        """ Return list of pages as a flattened list """

        parent = pgelem['/Parent'].get_object()
        pages = []

        while parent['/Type'] == '/Pages':
            pages.extend(parent['/Kids'])
            try:
                parent = parent['/Parent'].get_object()
            except KeyError:
                break

        pages = [pg.get_object() for pg in pages if pg != None]
        return pages
            
    def awamHandler(self,element):
        # Do the A-WAM checks on PDF structure element.
        # Applicability: /Document
        # Increase element count
        self.elementCount+=1

        # Verify that /S exists
        try:
            structureType=element['/S']
        except:
            return

        if structureType=='/Link':
            # import pdb; pdb.set_trace()
            # If properly specified, this should have a kid
            # of type '/OBJR' which points to the actual
            # link object.
            try:
                kids = element['/K']
                # This need not be a list, in that case put in a list
                # since we don't want to miss objects due to PDF
                # vagueness !
                if type(kids) not in (list, ArrayObject):
                    kids = [kids]
                    
                for kid in kids:
                    try:
                        kid  = kid.get_object()
                        # If this is not a dictionary object, skip it
                        if type(kid) not in (dict, DictionaryObject):
                            continue
                        
                        kidTyp = kid['/Type']

                        if kidTyp == '/OBJR':
                            # Get the object and append a tuple of the
                            # object and the annotation to the list
                            try:
                                linkObj = kid['/Obj'].get_object()
                                linkObjId = id(linkObj)
                                if linkObjId not in self.linkAnnots:
                                    self.linkAnnots[id(linkObj)] = (linkObj, element)
                            except Exception as e:
                                pass
                    except Exception as e:
                        pass
            except Exception as e:
                pass
                        
        elif structureType in list(PdfTblStruct.typedict.keys()):
            if structureType=='/Table':

                try:
                    self.tableStruct = self.tableStructDict[id(element)]
                except KeyError:
                    self.tableStruct = PdfTblStruct()
                    self.tableStructDict[id(element)] = self.tableStruct

            try:
                # Find if this has a page element
                pg = element['/Pg']

                if not self.tableStruct.isPageSet():
                    # Find the page number
                    pages = self.getFlattenedPages(pg)

                    try:
                        pgnum = pages.index(pg) + 1
                        self.tableStruct.setPage(pgnum)
                    except ValueError:
                        pass
            except KeyError:
                pass
            
            
            try:
                self.tableStruct.add(element)
            except PdfTblStructInvalidException as e:
                pass
        
        # Applicability criterion: /Form
        elif structureType == '/Form':
            # For the time being, simply checking if the ['/K']['/Obj']
            # is there for all form elements, not inspecting deep into
            # it
            try:
                elem_acc = element['/K']['/Obj']
                self.nFormEls += 1
            except KeyError:
                # Mark failure and don't check further
                self.resultMap['EIAO.A.15.2.1.4.PDF.4.1'] = {(0, 1): 0}
                
        # Applicability criterion: /Document
        elif structureType == '/Document':
            # if not self.langcheck:
            if 0:
                # LANG AWAM is applicable
                # Check if /Lang attribute exists. Return "" if not.
                # AWAM indicator for /Lang in BWAM
                self.check(element,"EIAO.A.10.4.1.4.PDF.1.1","/Lang",Pass=1,Fail=0)
                # AWAM indicator for /lang in MWAM
                self.check(element,"EIAO.A.0.0.0.4.PDF.4.1","/Lang",Fail=None)

        # Applicability criterion: Element /Figure
        elif structureType == '/Figure':
            try:
                self.figureEls.index(element)
            except ValueError:
                # Check if /Alt attribute exists.
                # NOTE: If self.validateImgs is False, the AWAM values would be already
                # updated after this step, so the if block below doesn't execute                
                r1=self.check(element,"EIAO.A.10.1.1.4.PDF.1.1","/Alt",Pass=1,Fail=0,
                              noAdd=self.validateImgs)
                # Check if /ActualText attribute exists.

                # NOTE: If self.validateImgs is False, the AWAM values would be already
                # updated after this step, so the if block below doesn't execute
                r2=self.check(element,"EIAO.A.10.1.1.4.PDF.2.1","/ActualText",Pass=1,Fail=0,
                              noAdd=self.validateImgs)

                pgnum, checked = 0, False
                
                if self.validateImgs:
                    # Validate images without alt by getting the page element
                    # for the image and validating whether this really is
                    # a page with images. Sometimes the structure tree seems
                    # to contain inconsistent data w.r.t the actual page
                    # so this check is often useful.
                    try:
                        pg = element['/Pg']
                        # Find which page is this by looking at the index
                        pgnum, pages = 1, self.getFlattenedPages(pg)

                        for page in pages:
                            pgobj = page.get_object()
                            if pgobj == pg:
                                # This is the page, validate the page
                                res = pg['/Resources'].get_object()
                                try:
                                    xobj = res['/XObject'].get_object()
                                    imgs=[item.get_object() for item in list(xobj.values()) if \
                                          item.get_object().get('/Subtype') in ('/Image')]

                                    if any(imgs):
                                        # Get the bit-depth of the images - if single bit
                                        # need to check against config
                                        if self.ignore1bitimgs:
                                            try:
                                                bits = [(img.get_object()['/BitsPerComponent'] != 1) for img in imgs]
                                                # If any img is not 1 bit, then fine, else don't
                                                # consider this result
                                                if not any(bits):
                                                    return
                                            except KeyError:
                                                pass
                                        checked = True
                                except KeyError:
                                    pass
                                break
                            pgnum += 1
                    except KeyError:
                        pass

                    # If not cross-checked reset page number
                    # if not checked: pgnum = 0
                    # We are adding the correct location of the image
                    # NOTE: This is conditionally put inside the if block because
                    # if validateImgs is True, then the resultmap for these keys
                    # won't be added, so we are adding them here.
                    self.resultMap["EIAO.A.10.1.1.4.PDF.2.1"][(pgnum,self.elementCount)] = r1
                    self.resultMap["EIAO.A.10.1.1.4.PDF.1.1"][(pgnum,self.elementCount)] = r2
                    if (not r1) and (not r2):                    
                        try:
                            self.failedImgs[pgnum].append(element)
                        except KeyError:
                            self.failedImgs[pgnum] = [element]
                else:
                    if (not r1) and (not r2):
                        try:
                            self.failedImgs[0].append(element)
                        except KeyError:
                            self.failedImgs[0] = [element]

                # Add entry for element
                self.figureEls.append(element)

        # Applicability criterion: role /Figure
        try:
            role = self.roleMap[structureType]
            if role == '/Figure':
                try:
                    self.figureEls.index(element)
                except ValueError:
                    # Check if /Alt attribute exists. 
                    self.check(element,"EIAO.A.10.1.1.4.PDF.1.1","/Alt",Pass=1,Fail=0)
                    # Check if /ActualText attribute exists.
                    self.check(element,"EIAO.A.10.1.1.4.PDF.2.1","/ActualText",Pass=1,Fail=0)
                    # Add entry for element
                    self.figureEls.append(element)
        except:
            # No roles defined
            pass


if __name__ == '__main__':
    # Test module
    a = PdfAWAMHandler(debug=1)
    pdfElement={'/Lang': 'no-NO', '/S': '/Document'}
    a.awamHandler(pdfElement)
    print(a.resultMap)
    
