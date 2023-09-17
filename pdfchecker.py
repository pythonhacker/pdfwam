""" Command-line PDF accessibility checker using PDF-WAM """

import pdfAWAM
import sys
import optparse
import config
import requests
import io

USAGE="""%s [options] pdffile - Check PDF documents for accessibility"""

def checkAcc(pdffile_or_url, passwd='', verbose=True, report=False,
             developer=False, loglevel='info', json_value=False):

    config.pdfwamloglevel = loglevel

    if pdffile_or_url.startswith('http://') or pdffile_or_url.startswith('https://'):
        data = requests.get(pdffile_or_url).content
        stream = io.BytesIO(data)
    else:
        stream = open(pdffile_or_url, 'rb')
        
    ret = pdfAWAM.extractAWAMIndicators(stream, passwd, verbose, report,
                                        developer, json_value, console=True)
    if developer:
        print(ret)

def setupOptions():
    if len(sys.argv)==1:
        sys.argv.append('-h')
        
    o = optparse.OptionParser(usage=USAGE % sys.argv[0] )
    o.add_option('-p','--password',
                 dest='password',help='Optional password for encrypted PDF',default='')
    o.add_option('-q','--quiet',
                 dest='quiet',help="Be quiet, won't print debug/informational messages",action="store_true",
                 default=False)
    o.add_option('-d','--developer',
                 dest='developer',help="Print a dictionary of information for the developer (please note that this turns off reporting and debug messages automatically)",action="store_true",
                 default=False)    
    o.add_option('-r','--report',
                 dest='report',help="Print a report of test results at the end",action="store_true",
                 default=False)
    o.add_option('-l','--loglevel',
                 dest='loglevel',help="Set logging level (default: info)",
                 default='info')
    o.add_option('-j', '--json',
                 dest='json', help="Print JSON of result",action="store_true",
                 default=False)

    options, args = o.parse_args()
    return (args[0], options.__dict__)

def main():
    pdffile, options = setupOptions()

    password = options.get('password','')
    quiet = options.get('quiet')
    report = options.get('report')
    developer = options.get('developer')
    loglevel = options.get('loglevel','info')
    json_flag = options.get('json')

    if developer:
        print('Developer option turned on, reporting and messages will be disabled.')

    verbose = (not quiet)
    checkAcc(pdffile, password, verbose, report, developer, loglevel, json_flag)

if __name__ == "__main__":
    main()
