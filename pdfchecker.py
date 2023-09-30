""" Command-line PDF accessibility checker using PDF-WAM """

import pdfAWAM
import sys
import optparse
import config
import requests
import io

USAGE="""%s [options] pdffile - Check PDF documents for accessibility"""

def checkAcc(pdffile_or_url, passwd='', verbose=False, report=False, json_value=False):

    if pdffile_or_url.startswith('http://') or pdffile_or_url.startswith('https://'):
        data = requests.get(pdffile_or_url).content
        stream = io.BytesIO(data)
    else:
        stream = open(pdffile_or_url, 'rb')
        
    ret = pdfAWAM.extractAWAMIndicators(stream, passwd, verbose, report,
                                        json_value, console=True)
    # import pdb;pdb.set_trace()
    if verbose:
        print(ret)
    return ret

def setupOptions():
    if len(sys.argv)==1:
        sys.argv.append('-h')
        
    o = optparse.OptionParser(usage=USAGE % sys.argv[0] )
    o.add_option('-p','--password',
                 dest='password',help='Optional password for encrypted PDF',default='')
    o.add_option('-v','--verbose',
                 dest='verbose',help="Print additional debug/informational messages",action="store_true",
                 default=False)
    o.add_option('-r','--report',
                 dest='report',help="Print a report of test results at the end",action="store_true",
                 default=False)
    o.add_option('-j', '--json',
                 dest='json', help="Print JSON of result",action="store_true",
                 default=False)

    options, args = o.parse_args()
    return (args[0], options.__dict__)

def main():
    pdffile, options = setupOptions()

    password = options.get('password','')
    verbose = options.get('verbose')
    report = options.get('report')
    json_flag = options.get('json')
    checkAcc(pdffile, password, verbose, report, json_flag)

if __name__ == "__main__":
    main()
