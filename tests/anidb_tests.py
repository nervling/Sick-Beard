# coding=UTF-8
import unittest
import test_lib as test

import sys, os.path
sys.path.append(os.path.abspath('..'))
sys.path.append(os.path.abspath('../lib'))
import sickbeard
from sickbeard.helpers import *
    
class AnidbBasicTests(test.SickbeardTestConfigCase):
    
    def setUp(self):
        tmpConnection = sickbeard.ADBA_CONNECTION
        super(AnidbBasicTests, self).setUp()
        sickbeard.ADBA_CONNECTION = tmpConnection
        
        
    def test_createConnection(self):
        # "disable" this test because running it withou the right config will fail. and i cant skip it since py2.6 does not understand it
        return True
        self.assertTrue(set_up_anidb_connection());
    
    def test_lookup(self):
        # "disable" this test because running it withou the right config will fail. and i cant skip it since py2.6 does not understand it 
        return True
        if set_up_anidb_connection():
            pass
        else:
            self.fail("Can not setup a connection. Check Username and password in config")
    
if __name__ == '__main__':
    print "=================="
    print "STARTING - ANIDB TESTS"
    print "=================="
    print "######################################################################"
    suite = unittest.TestLoader().loadTestsFromTestCase(AnidbBasicTests)
    unittest.TextTestRunner(verbosity=2).run(suite)