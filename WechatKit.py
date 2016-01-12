#!/usr/bin/env python
# coding=utf-8

import os
import urllib, urllib2
import re
import cookielib
import time
import xml.dom.minidom
import json
import sys
import math

'''
This class is based on https://github.com/0x5e/wechat-deleted-friends
some efforts are taken to make the code more OOP and readable.
Logining and processing are treated as independent procedures.   
'''
class WechatKit:
    DEBUG = False
    MAX_GROUP_NUM = 35 # 每组人数
    
    qrImagePath = ''
    resultFileName = ''
    cookieFileName = ''
    extraFileName = ''

    tip = 0
    uuid = ''

    baseUri = ''
    redirectUri = ''

    skey = ''
    wxsid = ''
    wxuin = ''
    passTicket = ''
    deviceId = 'e000000000000000'

    baseRequest = {}
    contactList = []
    myself = []
    cookieJar = None
    
    def __init__(self, workdir, id):
        self.qrImagePath = workdir + ('/%s-qrcode.jpg' % id)
        self.resultFileName = workdir + ('/%s-result.txt' % id)
        self.cookieFileName = workdir + ('/%s-key.ck' % id)
        self.extraFileName = workdir + ('/%s-ext.txt' % id)

    def _getUUID(self):
        url = 'https://login.weixin.qq.com/jslogin'
        params = {
            'appid': 'wx782c26e4c19acffb',
            'fun': 'new',
            'lang': 'zh_CN',
            '_': int(time.time()),
        }

        request = urllib2.Request(url = url, data = urllib.urlencode(params))
        response = urllib2.urlopen(request)
        data = response.read()

        # window.QRLogin.code = 200; window.QRLogin.uuid = "oZwt_bFfRg==";
        regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
        pm = re.search(regx, data)

        code = pm.group(1)
        if code == '200':
            self.uuid = pm.group(2)
            return True

        return False

    def _saveQRImage(self):
        url = 'https://login.weixin.qq.com/qrcode/' + self.uuid
        params = {
            't': 'webwx',
            '_': int(time.time()),
        }

        request = urllib2.Request(url = url, data = urllib.urlencode(params))
        response = urllib2.urlopen(request)

        self.tip = 1
        print "save file %s" % self.qrImagePath
        f = open(self.qrImagePath, 'wb')
        f.write(response.read())
        f.close()
        #self._showQRImage()

    def _showQRImage(self):
        if sys.platform.find('darwin') >= 0:
            os.system('open %s' % self.qrImagePath)
        elif sys.platform.find('linux') >= 0:
            os.system('xdg-open %s' % self.qrImagePath)
        else:
            os.system('call %s' % self.qrImagePath)
            

    def _checkLoginResult(self):
        url = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s' % (self.tip, self.uuid, int(time.time()))
        request = urllib2.Request(url = url)
        response = urllib2.urlopen(request)
        data = response.read()
        
        # print data
        # window.code=500;
        regx = r'window.code=(\d+);'
        pm = re.search(regx, data)
        code = pm.group(1)

        if code == '201': #已扫描
            print '成功扫描,请点击登陆'
            self.tip = 0
        elif code == '200': #已登录
            print '登陆成功'
            regx = r'window.redirect_uri="(\S+?)";'
            pm = re.search(regx, data)
            self.redirectUri = pm.group(1) + '&fun=new'
            self.baseUri = self.redirectUri[:self.redirectUri.rfind('/')]
        elif code == '408': #超时
            print '登陆超时'
        # elif code == '400' or code == '500':
        return code
        
    def _log(self, msg, debug=False):
        if not debug:
            print msg
        if debug and self.DEBUG:
            print msg

    def _getLoginToken(self):
        request = urllib2.Request(url = self.redirectUri)
        response = urllib2.urlopen(request)
        data = response.read()
        self._log(data, True);

        '''
            <error>
                <ret>0</ret>
                <message>OK</message>
                <skey>xxx</skey>
                <wxsid>xxx</wxsid>
                <wxuin>xxx</wxuin>
                <pass_ticket>xxx</pass_ticket>
                <isgrayscale>1</isgrayscale>
            </error>
        '''

        doc = xml.dom.minidom.parseString(data)
        root = doc.documentElement

        for node in root.childNodes:
            if node.nodeName == 'skey':
                self.skey = node.childNodes[0].data
            elif node.nodeName == 'wxsid':
                self.wxsid = node.childNodes[0].data
            elif node.nodeName == 'wxuin':
                self.wxuin = node.childNodes[0].data
            elif node.nodeName == 'pass_ticket':
                self.passTicket = node.childNodes[0].data

        self._log('skey: %s, wxsid: %s, wxuin: %s, pass_ticket: %s' % (self.skey, self.wxsid, self.wxuin, self.passTicket), True)

        if self.skey == '' or self.wxsid == '' or self.wxuin == '' or self.passTicket == '':
            return False

        self.baseRequest = {
            'Uin': int(self.wxuin),
            'Sid': self.wxsid,
            'Skey': self.skey,
            'DeviceID': self.deviceId,
        }
        return True

    def _getLoginInitData(self):
        url = self.baseUri + '/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (self.passTicket, self.skey, int(time.time()))
        params = {
            'BaseRequest': self.baseRequest
        }

        request = urllib2.Request(url = url, data = json.dumps(params))
        request.add_header('ContentType', 'application/json; charset=UTF-8')
        response = urllib2.urlopen(request)
        data = response.read()
        self._log(data, True)
        
        dic = json.loads(data)
        self.contactList = dic['ContactList']
        self.myself = dic['User']

        self.errMsg = dic['BaseResponse']['ErrMsg']
        # if len(errMsg) > 0:
        #     print errMsg

        res = dic['BaseResponse']['Ret']
        if res != 0:
            return False
            
        return True

    def _getFriendList(self):
        url = self.baseUri + '/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' % (self.passTicket, self.skey, int(time.time()))

        request = urllib2.Request(url = url)
        request.add_header('ContentType', 'application/json; charset=UTF-8')
        response = urllib2.urlopen(request)
        data = response.read()
        self._log(data, True)

        dic = json.loads(data)
        memberList = dic['MemberList']

        # 倒序遍历,不然删除的时候出问题..
        SpecialUsers = ['newsapp', 'fmessage', 'filehelper', 'weibo',
            'qqmail', 'fmessage', 'tmessage', 'qmessage', 'qqsync',
            'floatbottle', 'lbsapp', 'shakeapp', 'medianote', 'qqfriend',
            'readerapp', 'blogapp', 'facebookapp', 'masssendapp', 'meishiapp',
            'feedsapp', 'voip', 'blogappweixin', 'weixin', 'brandsessionholder',
            'weixinreminder', 'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'officialaccounts',
            'notification_messages', 'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'wxitil',
            'userexperience_alarm', 'notification_messages']

        for i in xrange(len(memberList) - 1, -1, -1):
            member = memberList[i]
            if member['VerifyFlag'] & 8 != 0: # 公众号/服务号
                memberList.remove(member)
            elif member['UserName'] in SpecialUsers: # 特殊账号
                memberList.remove(member)
            elif member['UserName'].find('@@') != -1: # 群聊
                memberList.remove(member)
            elif member['UserName'] == self.myself['UserName']: # 自己
                memberList.remove(member)

        return memberList

    def _createChatroom(self, userNames):
        memberList = []
        for userName in userNames:
            memberList.append({'UserName': userName})

        url = self.baseUri + '/webwxcreatechatroom?pass_ticket=%s&r=%s' % (self.passTicket, int(time.time()))
        params = {
            'BaseRequest': self.baseRequest,
            'MemberCount': len(memberList),
            'MemberList': memberList,
            'Topic': '',
        }

        request = urllib2.Request(url = url, data = json.dumps(params))
        request.add_header('ContentType', 'application/json; charset=UTF-8')
        response = urllib2.urlopen(request)
        data = response.read()
        self._log(data, True)

        dic = json.loads(data)
        chatRoomName = dic['ChatRoomName']
        memberList = dic['MemberList']
        deletedList = []
        for member in memberList:
            if member['MemberStatus'] == 4: #被对方删除了
                deletedList.append(member['UserName'])

        errMsg = dic['BaseResponse']['ErrMsg']
        # if len(errMsg) > 0:
        #     print errMsg

        return chatRoomName, deletedList

    def _removeFromChatroom(self, chatRoomName, userNames):
        url = self.baseUri + '/webwxupdatechatroom?fun=delmember&pass_ticket=%s' % (self.passTicket)
        params = {
            'BaseRequest': self.baseRequest,
            'ChatRoomName': chatRoomName,
            'DelMemberList': ','.join(userNames),
        }

        request = urllib2.Request(url = url, data = json.dumps(params))
        request.add_header('ContentType', 'application/json; charset=UTF-8')
        response = urllib2.urlopen(request)
        data = response.read()
        self._log(data, True)

        dic = json.loads(data)
        errMsg = dic['BaseResponse']['ErrMsg']
        # if len(errMsg) > 0:
        #     print errMsg

        ret = dic['BaseResponse']['Ret']
        if ret != 0:
            return False
            
        return True

    def _addToChatroom(self, chatRoomName, userNames):
        url = self.baseUri + '/webwxupdatechatroom?fun=addmember&pass_ticket=%s' % (self.passTicket)
        params = {
            'BaseRequest': self.baseRequest,
            'ChatRoomName': chatRoomName,
            'AddMemberList': ','.join(userNames),
        }

        request = urllib2.Request(url = url, data = json.dumps(params))
        request.add_header('ContentType', 'application/json; charset=UTF-8')
        response = urllib2.urlopen(request)
        data = response.read()
        self._log(data, True)

        dic = json.loads(data)
        memberList = dic['MemberList']
        deletedList = []
        for member in memberList:
            if member['MemberStatus'] == 4: #被对方删除了
                deletedList.append(member['UserName'])

        errMsg = dic['BaseResponse']['ErrMsg']
        # if len(errMsg) > 0:
        #     print errMsg

        return deletedList

    def requestLogin(self):
        self.cookieJar = cookielib.LWPCookieJar(self.cookieFileName)
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookieJar))
        urllib2.install_opener(opener)
        
        if not self._getUUID():
            print '获取uuid失败'
            return

        self._saveQRImage()
        self.cookieJar.save(self.cookieFileName)

        extraFile = open(self.extraFileName, 'w')
        extraFile.write(self.uuid)
        extraFile.close()
        
        self._log('二维码生成在%s下，打开以扫描登录' % self.qrImagePath)

    def checkLogin(self):
        self.cookieJar = cookielib.LWPCookieJar(self.cookieFileName)
        self.cookieJar.load(self.cookieFileName)
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookieJar))
        urllib2.install_opener(opener)

        extraFile = open(self.extraFileName, 'r')
        self.uuid = extraFile.read(os.path.getsize(self.extraFileName))
        extraFile.close()
        # self._log('uuid ' + self.uuid, False)

        resCode = self._checkLoginResult()
        if resCode != '200':
            print "你没有扫描或者登陆失败, code: " + resCode
            return

        #os.remove(qrImagePath)
        if not self._getLoginToken():
            print '登录失败'
            return

        if not self._getLoginInitData():
            print '初始化失败'
            return

        memberList = self._getFriendList()
        memberCount = len(memberList)
        print '通讯录共%s位好友' % memberCount

        chatRoomName = ''
        result = []
        #print '开始查找...'
        group_num=int(math.ceil(memberCount / float(self.MAX_GROUP_NUM)))
        for i in xrange(0, group_num):
            userNames = []
            nickNames = []
            for j in xrange(0, self.MAX_GROUP_NUM):
                if i * self.MAX_GROUP_NUM + j >= memberCount:
                    break
                Member = memberList[i * self.MAX_GROUP_NUM + j]
                userNames.append(Member['UserName'])
                nickNames.append(Member['NickName'].encode('utf-8'))

            #     进度条
            #progress='-'*10
            #progress_str='%s'%''.join(map(lambda x:'#',progress[:(10*(i+1))/group_num]))
            #print '[',progress_str,''.join('-'*(10-len(progress_str))),']',
            #print '(当前,你被%d人删除,好友共%d人'%(len(result),len(memberList)),'\r',

            # print '第%s组...' % (i + 1)
            # print ', '.join(nickNames)
            # print '回车键继续...'
            # raw_input()

            # 新建群组/添加成员
            if chatRoomName == '':
                (chatRoomName, deletedList) = self._createChatroom(userNames)
            else:
                deletedList = self._addToChatroom(chatRoomName, userNames)

            deletedCount = len(deletedList)
            if deletedCount > 0:
                result += deletedList

            # 删除成员
            self._removeFromChatroom(chatRoomName, userNames)

        resultNames = []
        for member in memberList:
            if member['UserName'] in result:
                nickName = member['NickName']
                if member['RemarkName'] != '':
                    nickName += '(%s)' % member['RemarkName']
                resultNames.append(nickName.encode('utf-8'))

        print "\n---------- 下面是删除了你的好友 ----------\n"
        resultNames = map(lambda x:re.sub(r'<span.+/span>','',x),resultNames)
        print '\n'.join(resultNames)
        print '---------- 没关系，有些人总是要走的，清理一下，愉快出发吧~ ----------'

        '''
        logFile = open(self.resultFileName, 'w')
        logFile.write("---------- 你的这些好友删除了你 ----------")
        logFile.write('\n'.join(resultNames))
        logFile.write('---------- 没关系，有些人总是要走的 ----------')
        logFile.close()
        '''

    def _cleanup(self):
        #todo remote temp files here.
        pass


# windows下编码问题修复
# http://blog.csdn.net/heyuxuanzee/article/details/8442718
class UnicodeStreamFilter:  
    def __init__(self, target):  
        self.target = target  
        self.encoding = 'utf-8'  
        self.errors = 'replace'  
        self.encode_to = self.target.encoding  
        
    def write(self, s):  
        if type(s) == str:  
            s = s.decode('utf-8')  
        s = s.encode(self.encode_to, self.errors).decode(self.encode_to)  
        self.target.write(s)  

if __name__ == '__main__' :
    if sys.stdout.encoding == 'cp936':  
        sys.stdout = UnicodeStreamFilter(sys.stdout)
       
    if len(sys.argv)<3:
        print "usage <id> login|process"
        exit()
        
    kit = WechatKit(os.getcwd() + "/", sys.argv[1])
    if sys.argv[2] == 'login':
        kit.requestLogin()
    else:
        kit.checkLogin()
