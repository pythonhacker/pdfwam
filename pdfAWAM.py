"""
pdfAWAM - Entry point into PDF accessibility checker

"""

from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

import pdfwcag
import logging
import config

import time
import io
import traceback

class PdfInitException(Exception):
    """ Errors initializing the PDF file """

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class DecryptionFailedException(Exception):
    """ Errors in decrypting an encrypted PDF file """

class PdfWamProcessingError(Exception):
    """ Class summarizing all PDF-WAM processing exceptions """

class PdfReaderWrapper(PdfReader, pdfwcag.PdfWCAG):
    """ Our own customized Pdf file reader class
    which inherits from the pyPdf one """
    
    def __init__(self, stream, password='', logger=None):
        self._override_encryption = False
        self._encryption = None
        self.passwd = password
        self.xrefIndex = 0
        self.strict = False
        self.logger = logger
        self.stream = stream
        # Rewind stream to beginning
        pdfwcag.PdfWCAG.__init__(self, stream=stream)
        PdfReader.__init__(self, stream)
        # PdfStructureMixin.read(self, stream)
        # Fill in document information
        self.fill_info()
        # Set the root object
        self.root =  self.trailer['/Root'].get_object()
    
def extractAWAMIndicators(pdf,
                          password='',
                          verbose=True,
                          report=False,
                          developer=False,
                          json_value=False,
                          console=False,
                          logger=None):
    """ Check whether the given PDF document is accessible """

    t = time.time()
    print('Log level is set to',config.pdfwamloglevel)

    if logger == None:
        logger = logging.getLogger('pdfawam')
    
    # Takes an optional password which can be used to
    # unlock the document for encrypted documents.
    try:
        # pdfobj = MyPdfFileReader(pdf, password, logger)
        pdfobj = PdfReaderWrapper(pdf, password, logger)
        pdfobj.verbose = verbose
        
        # pdfobj.read()
        pdfobj.fix_indirect_object_xref()

        # If developer, just print a dictionary containing
        # meta info, scanned, forms, tagged, permissions
        # and an accessibility score.
        if developer:
            pdfobj.init()
            pdfobj.process_awam()            
            devdict = { 'title': pdfobj.title,
                        'creator': pdfobj.creator,
                        'producer': pdfobj.producer,
                        'author': pdfobj.author,
                        'subject': pdfobj.subject,
                        'created': pdfobj.ctime,
                        'scanned': pdfobj.is_scanned,
                        'tagged': (pdfobj.struct_tree != None),
                        'form': pdfobj.has_valid_forms(),
                        'permissions': pdfobj.awamHandler.resultMap['EIAO.A.10.8.1.4.PDF.1.1'].get((0,1),0),
                        'lang': pdfobj.awamHandler.resultMap.get('EIAO.A.0.0.0.0.4.PDF.4.1',''),
                        'numpages': len(pdfobj.pages)
                        }
            
            return devdict
        
        if verbose:
            # NOTE - These are supposed to be printed to STDOUT
            # so don't wrap them in logging !
            
            print("***PDF Summary: Start***")
            print('Version:',pdfobj.version)
            print('#Pages:', len(pdfobj.pages))
            print('Producer:',pdfobj.producer)
            print('Creator:',pdfobj.creator)
            if pdfobj.title:
                print('Title=>',pdfobj.title)
            else:
                print('Title: (None)')

            print('Has structure tree:',(pdfobj.struct_tree != None))
            print('Has forms:', pdfobj.has_forms())
            print('Has bookmarks:',pdfobj.has_bookmarks())
            print('Scanned:',pdfobj.is_scanned)
            print('Num Images:',pdfobj.get_num_images())

            print('***PDF Summary: End ****\n')

        pdfobj.run_all_tests()
    except DecryptionFailedException:
        # We are unable to decrypt document.
        # We have got no parsed pdfobj, and cannot do much more,
        # unfortunately... 
        # Tell that the document was not accessible due to encryption, at least
        errmsg="Document Decryption failed"
        logger.error(errmsg)
        # Ticket 127 fix
        # return {}
        raise PdfWamProcessingError(errmsg)
    except NotImplementedError:
        # pyPdf only supports algorithm version 1 and 2. 
        # Version 3 and 4 are not yet supported.
        errmsg="Unsupported decryption algorithm."
        logger.error(errmsg)
        # Ticket 127 fix        
        raise PdfWamProcessingError(errmsg) 
    except PdfReadError as e:
        errmsg='Error, cannot read PDF file: ' + str(e)
        logger.error(errmsg)
        # Not a PDF file
        # return {}
        raise PdfWamProcessingError(errmsg)
    except Exception as e:
        # Final global catch-all handler
        # Prepare error message
        message = "%s : %s" % (e.__class__.__name__, str(e))

        # Save traceback
        capture = io.StringIO()
        traceback.print_exc(file=capture)
        logger.error(message)
        logger.error("Traceback")
        logger.error(capture.getvalue())

        raise PdfWamProcessingError("Unguarded error => [" + message + " ] <=. Please send feedback to developers.")
    
    logger.info('Processed in %.2f seconds' % (time.time() - t))
    rmap = pdfobj.awamHandler.resultMap
    logger.debug('\n***AWAM Dictionary***')
    logger.debug(rmap)

    if verbose:
        for id in list(rmap.keys()):
            value = rmap[id]
            if type(value) is dict:
                for location in list(value.keys()):
                    print('AWAM-ID:',id,' location:',location,' value:',value[location])
            else:
                print('AWAM-ID:',id,'value:',value)
            
    if report:
        pdfobj.print_report()

    print('-'*80)

    if json_value:
        return pdfobj.get_json()

    return rmap
        

    

