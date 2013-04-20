# Author: Kyle Klein <kyletklein@gmail.com>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.

import httplib
import re
import urllib2

from base64 import b64encode

try:
    import json
except ImportError:
    from lib import simplejson as json

import sickbeard

from sickbeard import helpers
from sickbeard import logger
from sickbeard.exceptions import ex

def sendTorrent(torrent):
  """
  Sends a torrent to transmission via the web ui.

  torrent: The TorrentSearchResult object to send to Transmission.
  """
  data = helpers.getURL(torrent.url)
  params = {'download-dir' : sickbeard.TRANSMISSION_DOWNLOAD_DIR}
  try :
    trpc = TransmissionRPC(url = sickbeard.TRANSMISSION_HOST, username = sickbeard.TRANSMISSION_USERNAME, password = sickbeard.TRANSMISSION_PASSWORD)
    return trpc.add_torrent_file(b64encode(data), arguments = params)
  except Exception as e:
    logger.log(u"Error sending to tranmission:" + ex(e), logger.ERROR)
    return False

class TransmissionRPC(object):

    """TransmissionRPC lite library Adapted from CouchPotatoServer."""

    def __init__(self, url = 'http://localhost:9091/', username = None, password = None):

        super(TransmissionRPC, self).__init__()

        self.url = url + "transmission/rpc"
        self.tag = 0
        self.session_id = 0
        self.session = {}
        if username and password:
            password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
            password_manager.add_password(realm = None, uri = self.url, user = username, passwd = password)
            opener = urllib2.build_opener(urllib2.HTTPBasicAuthHandler(password_manager), urllib2.HTTPDigestAuthHandler(password_manager))
            opener.addheaders = [('User-agent', 'couchpotato-transmission-client/1.0')]
            urllib2.install_opener(opener)
        elif username or password:
            logger.log(u"User or password missing, not using authentication.", logger.DEBUG)
        self.session = self.get_session()

    def _request(self, ojson):
        self.tag += 1
        headers = {'x-transmission-session-id': str(self.session_id)}
        request = urllib2.Request(self.url, json.dumps(ojson).encode('utf-8'), headers)
        try:
            open_request = urllib2.urlopen(request)
            response = json.loads(open_request.read())
            logger.log(u"Transmission request: " +  str(json.dumps(ojson)), logger.DEBUG)
            logger.log(u"Transmission response: " + str(json.dumps(response)), logger.DEBUG)
            if response['result'] == 'success':
                logger.log(u"Transmission action successfull", logger.DEBUG)
                return response['arguments']
            else:
                logger.log(u"Unknown failure sending command to Transmission. Return text is: " + str(response['result']), logger.ERROR)
                return False
        except httplib.InvalidURL, err:
            logger.log(u"Invalid Transmission host, check your config: " + ex(err), logger.ERROR)
            return False
        except urllib2.HTTPError, err:
            if err.code == 401:
                logger.log(u"Invalid Transmission Username or Password, check your config", logger.ERROR)
                return False
            elif err.code == 409:
                msg = str(err.read())
                try:
                    self.session_id = \
                        re.search('X-Transmission-Session-Id:\s*(\w+)', msg).group(1)
                    logger.log(u"X-Transmission-Session-Id: " + str(self.session_id), logger.DEBUG)

                    # #resend request with the updated header

                    return self._request(ojson)
                except Exception as e:
                    logger.log(u"Unable to get Transmission Session-Id " + str(err) + " " + msg, logger.ERROR)
                    logger.log(u"Transmission Session-Id Error: " + ex(e), logger.ERROR)
                    return False
            else:
                logger.log(u"TransmissionRPC HTTPError: " + str(err), logger.ERROR)
                return False
        except urllib2.URLError, err:
            logger.log(u"Unable to connect to Transmission " + str(err), logger.ERROR)
            return False

    def get_session(self):
        post_data = {'method': 'session-get', 'tag': self.tag}
        return self._request(post_data)

    def add_torrent_uri(self, torrent, arguments):
        arguments['filename'] = torrent
        post_data = {'arguments': arguments, 'method': 'torrent-add', 'tag': self.tag}
        return self._request(post_data)

    def add_torrent_file(self, torrent, arguments):
        arguments['metainfo'] = torrent
        post_data = {'arguments': arguments, 'method': 'torrent-add', 'tag': self.tag}
        return self._request(post_data)

    def set_torrent(self, torrent_id, arguments):
        arguments['ids'] = torrent_id
        post_data = {'arguments': arguments, 'method': 'torrent-set', 'tag': self.tag}
        return self._request(post_data)

    def get_alltorrents(self, arguments):
        post_data = {'arguments': arguments, 'method': 'torrent-get', 'tag': self.tag}
        return self._request(post_data)

    def stop_torrent(self, torrent_id, arguments):
        arguments['ids'] = torrent_id
        post_data = {'arguments': arguments, 'method': 'torrent-stop', 'tag': self.tag}
        return self._request(post_data)

    def remove_torrent(self, torrent_id, remove_local_data, arguments):
        arguments['ids'] = torrent_id
        arguments['delete-local-data'] = remove_local_data
        post_data = {'arguments': arguments, 'method': 'torrent-remove', 'tag': self.tag}
        return self._request(post_data)
