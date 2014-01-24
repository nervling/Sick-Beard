# Author: Nic Wolfe <nic@wolfeden.ca>
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



import datetime
import os
import sys
import re
import urllib2

import sickbeard

from sickbeard import helpers, classes, logger, db, exceptions

from sickbeard.common import Quality, MULTI_EP_RESULT, SEASON_RESULT
from sickbeard import tvcache
from sickbeard import encodingKludge as ek
from sickbeard.exceptions import ex

from lib.hachoir_parser import createParser

from sickbeard.name_parser.parser import InvalidNameException
from sickbeard.completparser import CompleteParser

class GenericProvider:

    NZB = "nzb"
    TORRENT = "torrent"

    def __init__(self, name):

        # these need to be set in the subclass
        self.providerType = None
        self.name = name
        self.url = ''

        self.supportsBacklog = False
        self.supportsAbsoluteNumbering = False

        self.cache = tvcache.TVCache(self)

    def getID(self):
        return GenericProvider.makeID(self.name)

    @staticmethod
    def makeID(name):
        return re.sub("[^\w\d_]", "_", name).lower()

    def imageName(self):
        return self.getID() + '.png'

    def _checkAuth(self):
        return

    def isActive(self):
        if self.providerType == GenericProvider.NZB and sickbeard.USE_NZBS:
            return self.isEnabled()
        elif self.providerType == GenericProvider.TORRENT and sickbeard.USE_TORRENTS:
            return self.isEnabled()
        else:
            return False

    def isEnabled(self):
        """
        This should be overridden and should return the config setting eg. sickbeard.MYPROVIDER
        """
        return False

    def getResult(self, episodes):
        """
        Returns a result of the correct type for this provider
        """

        if self.providerType == GenericProvider.NZB:
            result = classes.NZBSearchResult(episodes)
        elif self.providerType == GenericProvider.TORRENT:
            result = classes.TorrentSearchResult(episodes)
        else:
            result = classes.SearchResult(episodes)
        
        result.provider = self    
            
        return result

    def getURL(self, url, headers=None):
        """
        By default this is just a simple urlopen call but this method should be overridden
        for providers with special URL requirements (like cookies)
        """

        if not headers:
            headers = []

        result = helpers.getURL(url, headers)

        if result is None:
            logger.log(u"Error loading "+self.name+" URL: " + url, logger.ERROR)
            return None

        return result
    
    def get_episode_search_strings(self,ep_obj):
        return self._get_episode_search_strings(ep_obj)
    
    def downloadResult(self, result):
        """
        Save the result to disk.
        """

        logger.log(u"Downloading a result from " + self.name+" at " + result.url)

        data = self.getURL(result.url)

        if data == None:
            return False

        # use the appropriate watch folder
        if self.providerType == GenericProvider.NZB:
            saveDir = sickbeard.NZB_DIR
            writeMode = 'w'
        elif self.providerType == GenericProvider.TORRENT:
            saveDir = sickbeard.TORRENT_DIR
            writeMode = 'wb'
        else:
            return False

        # use the result name as the filename
        fileName = ek.ek(os.path.join, saveDir, helpers.sanitizeFileName(result.name) + '.' + self.providerType)

        logger.log(u"Saving to " + fileName, logger.DEBUG)

        try:
            fileOut = open(fileName, writeMode)
            fileOut.write(data)
            fileOut.close()
            helpers.chmodAsParent(fileName)
        except IOError, e:
            logger.log("Unable to save the file: "+ex(e), logger.ERROR)
            return False

        # as long as it's a valid download then consider it a successful snatch
        return self._verify_download(fileName)

    def _verify_download(self, file_name=None):
        """
        Checks the saved file to see if it was actually valid, if not then consider the download a failure.
        """

        # primitive verification of torrents, just make sure we didn't get a text file or something
        if self.providerType == GenericProvider.TORRENT:
            parser = createParser(file_name)
            if parser:
                mime_type = parser._getMimeType()
                try:
                    parser.stream._input.close()
                except:
                    pass
                if mime_type != 'application/x-bittorrent':
                    logger.log(u"Result is not a valid torrent file", logger.WARNING)
                    return False

        return True

    def searchRSS(self):
        self.cache.updateCache()
        return self.cache.findNeededEpisodes()

    def getQuality(self, item, anime=False):
        """
        Figures out the quality of the given RSS item node
        
        item: An xml.dom.minidom.Node representing the <item> tag of the RSS feed
        
        Returns a Quality value obtained from the node's data 
        """
        (title, url) = self._get_title_and_url(item) #@UnusedVariable
        logger.log(u"geting quality for:" + title+ " anime: "+str(anime),logger.DEBUG)
        quality = Quality.sceneQuality(title, anime)
        return quality
    
    def _doSearch(self, show=None):
        return []

    def _get_season_search_strings(self, show, season, episode=None):
        return []

    def _get_episode_search_strings(self, ep_obj):
        return []
    
    def _get_title_and_url(self, item):
        """
        Retrieves the title and URL data from the item XML node

        item: An xml.dom.minidom.Node representing the <item> tag of the RSS feed

        Returns: A tuple containing two strings representing title and URL respectively
        """

        """we are here in the search provider it is ok to delete the /.
        i am doing this because some show get posted with a / in the name
        and during qulaity check it is reduced to the base name
        """
        title = helpers.get_xml_text(item.getElementsByTagName('title')[0]).replace("/"," ")
        try:
            url = helpers.get_xml_text(item.getElementsByTagName('link')[0])
            if url:
                url = url.replace('&amp;','&')
        except IndexError:
            url = None
        
        return (title, url)
    
    def findEpisode (self, episode, manualSearch=False, searchString=None):

        self._checkAuth()
        if searchString:
            logger.log(u"Searching "+self.name+" for " + episode.prettyName())
        else:
            logger.log(u"Searching "+self.name+" for episode " + episode.prettyName(True))

        self.cache.updateCache()
        results = self.cache.searchCache(episode, manualSearch)
        logger.log(u"Cache results: "+str(results), logger.DEBUG)

        # if we got some results then use them no matter what.
        # OR
        # return anyway unless we're doing a manual search
        if results or not manualSearch:
            return results

        if searchString: # if we already got a searchstring don't bother make one
            search_strings = [searchString]
        else:
            search_strings = self._get_episode_search_strings(episode)

        itemList = []
        for cur_search_string in search_strings:
            itemList += self._doSearch(cur_search_string, show=episode.show)


        for item in itemList:

            (title, url) = self._get_title_and_url(item)

            cp = CompleteParser(show=episode.show, tvdbActiveLookUp=True)
            cpr = cp.parse(title)

            parse_result = cpr.parse_result

            if episode.show.air_by_date:
                if parse_result.air_date != episode.airdate:
                    logger.log("Episode " + title + " didn't air on " + str(episode.airdate) + ", skipping it", logger.DEBUG)
                    continue
            elif cpr.season != episode.season or episode.episode not in cpr.episodes:
                logger.log("Episode " + title + " isn't " + str(episode.scene_season) + "x" + str(episode.scene_episode) + " (beware of scene conversion) , skipping it", logger.DEBUG)
                continue

            if not episode.show.wantEpisode(episode.season, episode.episode, cpr.quality, manualSearch):
                logger.log(u"Ignoring result " + title + " because we don't want an episode that is " + Quality.qualityStrings[cpr.quality], logger.DEBUG)
                continue

            logger.log(u"Found result " + title + " at " + url, logger.DEBUG)

            result = self.getResult([episode])
            result.url = url
            result.name = title
            result.quality = cpr.quality
            result.provider = self
            result.content = None 
            result.release_group = parse_result.release_group
            result.is_proper = cpr.is_proper
            
            results.append(result)

        return results

    def findSeasonResults(self, show, season, scene=False):

        itemList = []
        results = {}

        for curString in self._get_season_search_strings(show, season):
            itemList += self._doSearch(curString, show=show)

        for item in itemList:

            (title, url) = self._get_title_and_url(item)
            # parse the file name
            cp = CompleteParser(show=show)
            cpr = cp.parse(title)
            if not cpr:
                continue

            # make sure we want the episode
            wantEp = True
            for epNo in cpr.episodes:
                if not show.wantEpisode(cpr.season, epNo, cpr.quality):
                    wantEp = False
                    break

            if not wantEp:
                logger.log(u"Ignoring result "+title+" because we don't want an episode that is "+Quality.qualityStrings[cpr.quality], logger.DEBUG)
                continue

            logger.log(u"Found result " + title + " at " + url, logger.DEBUG)

            # make a result object
            epObj = []
            for curEp in cpr.episodes:
                epObj.append(show.getEpisode(cpr.season, curEp))

            result = self.getResult(epObj)
            result.url = url
            result.name = title
            result.quality = cpr.quality
            result.provider = self
            result.content = None 
            result.release_group = cpr.release_group
            result.is_proper = cpr.is_proper

            if len(epObj) == 1:
                epNum = epObj[0].episode
            elif len(epObj) > 1:
                epNum = MULTI_EP_RESULT
                logger.log(u"Separating multi-episode result to check for later - result contains episodes: " + str(cpr.episodes), logger.DEBUG)
            elif len(epObj) == 0:
                epNum = SEASON_RESULT
                result.extraInfo = [show]
                logger.log(u"Separating full season result to check for later", logger.DEBUG)

            if epNum in results:
                results[epNum].append(result)
            else:
                results[epNum] = [result]

        return results

    def findPropers(self, date=None):

        results = self.cache.listPropers(date)

        return [classes.Proper(x['name'], x['url'], datetime.datetime.fromtimestamp(x['time'])) for x in results]


class NZBProvider(GenericProvider):

    def __init__(self, name):

        GenericProvider.__init__(self, name)

        self.providerType = GenericProvider.NZB

class TorrentProvider(GenericProvider):

    def __init__(self, name):

        GenericProvider.__init__(self, name)

        self.providerType = GenericProvider.TORRENT
