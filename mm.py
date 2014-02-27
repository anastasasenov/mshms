#!/usr/bin/python
# -*- coding: utf-8 -*-

#################################
#
# Microshop Management System
#
# anastasasenov@hotmail.com
#
# lic: use it for free
#################################

import struct
import thread
import time
from math import trunc
from datetime import datetime
import sys
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import re
import os
import random
import sqlite3 as lite

# globals
g_maxRows    = 20
g_httpPort   = 8000
g_dbPrefix   = 'mm'
g_dbFile     = g_dbPrefix + '.db'
g_dbVersion  = '1.0'
g_sleep      = 0.1
g_title      = 'Microshop Management System'

# classes #

class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            key = self.path
            self.send_response(200)
            if (key == '/ajax'):
                self.send_header('Contetn-Type', 'text/xml')
            elif key == '/icon.png':
                self.send_header('Content-Type', 'image/png')
            else:
                self.send_header('Content-Type', 'text/html')
            self.end_headers()
            writeResponse(key, self.wfile)
        except Exception as e:
            self.send_error(500, 'Server Error' + str(type(e)) + str(e))
    def log_request(self, code='-', size='-'):
        pass


# functions #

def dbDump(con, sqlFile):
    if not os.path.isfile(sqlFile):
        data = '\n'.join(con.iterdump())
        f = open(sqlFile, 'w')
        with f:
            f.write(data)
            f.close()

def dbCreate(con):
    with con:   
       cur = con.cursor()
       cur.execute("CREATE TABLE nn_version(nn_version TEXT NOT NULL)")
       cur.executemany("INSERT INTO nn_version VALUES (?)", [ [ g_dbVersion ] ])
       cur.execute("CREATE TABLE nn_item (nn_item_id INTEGER PRIMARY KEY AUTOINCREMENT, nn_item_no TEXT NOT NULL, nn_item_name TEXT NOT NULL, nn_item_size TEXT NOT NULL, nn_item_provider TEXT NOT NULL, nn_item_dt TEXT NOT NULL)")
       cur.execute("CREATE UNIQUE INDEX nn_item_idx1 ON nn_item (nn_item_no, nn_item_size)")
       cur.execute("CREATE TABLE nn_stock (nn_stock_id INTEGER PRIMARY KEY AUTOINCREMENT, nn_stock_item_id INTEGER NOT NULL, nn_stock_number_of_items INTEGER NOT NULL, nn_stock_delivery_price INTEGER NOT NULL, nn_stock_customer_price INTEGER NOT NULL, nn_stock_delivery_dt TEXT NOT NULL, nn_stock_invoice_no TEXT NOT NULL)")
       cur.execute("CREATE TABLE nn_sell (nn_sell_id INTEGER PRIMARY KEY AUTOINCREMENT, nn_sell_stock_id INTEGER NOT NULL, nn_sell_number_of_items INTEGER NOT NULL, nn_sell_dt TEXT NOT NULL)")       
    
def dbRestore():
    dump = g_dbPrefix + '.sql'
    if os.path.isfile(dump) and not os.path.isfile(g_dbFile):
        f = open(dump, 'r')
        con = lite.connect(g_dbFile)
        con.executescript(f.read())
        f.close()
        con.close()

def dbVerify(con):
    #check version
    with con:
        cur = con.cursor()
        #cur.execute("PRAGMA encoding = \"UTF-8\"" );
        cur.execute("PRAGMA table_info(nn_version)")
        row = cur.fetchone()
        # todo fix db-structure
        if row == None:       
            dbCreate(con)

g_execLock = thread.allocate_lock()
g_stmt = ''
g_rows = None
g_skipRows = None
g_fetchRows = None
def dbExec(stmt, skipRows = None, fetchRows = None):
    global g_rows, g_stmt, g_skipRows, g_fetchRows
    g_execLock.acquire()
    while g_stmt != '':
        g_execLock.release()
        time.sleep(g_sleep * random.randint(1,7))
        g_execLock.acquire()
    g_stmt = stmt
    g_skipRows = skipRows
    g_fetchRows = fetchRows
    g_execLock.release()
    bFinished = False
    while not bFinished:
        time.sleep(g_sleep)
        g_execLock.acquire()
        if (g_stmt == ''):
            bFinished = True  
        g_execLock.release()
    return g_rows

def dbProcess(con):
    global g_rows, g_stmt, g_skipRows, g_fetchRows
    g_execLock.acquire()
    if "BEGIN" == g_stmt[:5]:
        g_rows = []
        con.executescript(g_stmt)
        #print g_stmt
    elif g_stmt != '':
        with con:   
            cur = con.cursor()
            #print g_stmt
            cur.execute(g_stmt)
            if g_skipRows == None:
                g_rows = cur.fetchall()
            else:
                if g_skipRows > 0:
                    cur.fetchmany(g_skipRows)
                g_rows = cur.fetchmany(g_fetchRows)
                #print g_stmt, g_rows
    g_stmt = ''
    g_execLock.release()        

def startServer():
    try:
        g_server.serve_forever()
    except KeyboardInterrupt:
        g_server.socket.close()

def unquote(val):
    #return urllib.unquote_plus(val)
    return re.compile('%([0-9a-fA-F]{2})',re.M).sub(lambda m: chr(int(m.group(1),16)), val)
    
def dbStockOffset(idStock, bWithEmptyPositions = True):
    statement = "SELECT count(*) FROM nn_stock WHERE nn_stock_id < " + str(idStock)
    if not bWithEmptyPositions:
        statement += " and nn_stock_number_of_items > 0"
    rows = dbExec(statement)
    if rows == []:
        return 0
    else:
        return rows[0][0]

def dbItemOffset(idItem):
    rows = dbExec("SELECT count(*) FROM nn_item WHERE nn_item_id < " + str(idItem))
    if rows == []:
        return 0
    else:
        return rows[0][0]

def writePagePrefix(f, title):
    f.write('<html>')
    f.write('<meta http-equiv="Content-Type" content="text/html; charset=utf-8">')
    f.write('<META HTTP-EQUIV="CACHE-CONTROL" CONTENT="NO-CACHE">')
    f.write('<head><title>' + title + '</title>')
    f.write('</head>')
    f.write('<body>')

def writePageSuffix(f):
    f.write('</body></html>\n')        

def writeMainPagePrefix(f):
    f.write('''
        <html>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
        <META HTTP-EQUIV="CACHE-CONTROL" CONTENT="NO-CACHE">
        <head><title>Microshop Management System</title>
        <script type="text/javascript">
        function is_empty(val) {
          return (!val || 0 == val.length);
        }
        function search_by_text() {
          req = new XMLHttpRequest();
          text = document.getElementById('search-text-sell').value;
          if (is_empty(text)) return;
          req.open("GET", "/search_by_text?text="+text, false);
          req.send();
          if(req.status == 200) {
            //window.alert(req.responseText);
            window.location.href = "/?g_stock_id=" + req.responseText;
          }  
        }
        function search_by_text_with_empty_positions() {
          req = new XMLHttpRequest();
          text = document.getElementById('search-text-stock').value;
          if (is_empty(text)) return;
          req.open("GET", "/search_by_text_with_empty_positions?text="+text, false);
          req.send();
          if(req.status == 200) {
            //window.alert(req.responseText);
            window.location.href = "/?g_stock_id=" + req.responseText + "&g_item_id=0";
          }  
        }
        function show_version() {
          req = new XMLHttpRequest();
          req.open("GET", "/show_version");
          req.send();
        }
        function add_item() { 
          itemNo = document.getElementById("item-no").value;
          itemName = document.getElementById("item-name").value;
          itemSize = document.getElementById("item-size").value;
          itemProvider = document.getElementById("item-provider").value;
          if (is_empty(itemNo) || is_empty(itemName) || is_empty(itemSize)) {
            alert("Empty item's attributes!!!");
            return;
          }
          req = new XMLHttpRequest();
          req.open("GET", "/add_item?no="+itemNo+'&name='+itemName+'&size='+itemSize+'&provider='+itemProvider, false);
          req.send();
          if(req.status == 200) {  
            if (is_empty(req.responseText)) alert("Insert error!!!");
            else {
              alert("Successfully added item " + req.responseText);             
              tbl = document.getElementById("item_table");
              if (is_empty(String(tbl.innerHTML).trim())) tbl.innerHTML += " <tr><td>No</td><td>Name</td><td>Size</td><td>Provider</td></tr> ";
              tbl.innerHTML += " <tr><td>" + itemNo + "</td><td>" + itemName + "</td><td>" + itemSize + "</td><td>" + itemProvider + "</td></tr> ";
            }
          }
          //setTimeout(function(){window.location.reload();},100);
          window.location.href = "#tab2";
        }
        function add_sell() { 
          numberOfItems = document.getElementById("number-of-items").value;
          stockId = document.getElementById("g_stock_id").value;  
          if (is_empty(numberOfItems) || is_empty(stockId)) {
            alert("Invalid number of items!!!");
            return;
          }
          req = new XMLHttpRequest();
          req.open("GET", "/add_sell?g_stock_id="+stockId+"&number="+numberOfItems, false);
          req.send();
          if(req.status == 200) {  
            if (is_empty(req.responseText)) alert("Insert error!!!");
            else alert("Successfully added sell " + req.responseText);
          }          
          setTimeout(function(){window.location.reload();},100);
        }
        function add_stock() {
          numberOfItems = document.getElementById("num-items").value;
          deliveryPrice = document.getElementById("delivery-price").value;
          customerPrice = document.getElementById("customer-price").value;
          stockId = document.getElementById("g_stock_id").value;    
          invoceNo = document.getElementById("invoice-no").value;
          if (is_empty(numberOfItems) || is_empty(deliveryPrice) || is_empty(customerPrice) || is_empty(stockId)) {
            alert("Непопълнени атрибути на доставка!!!");
            return;
          }
          req = new XMLHttpRequest();
          req.open("GET", "/add_stock?g_stock_id="+stockId+"&number="+numberOfItems+'&dprice='+deliveryPrice+'&cprice='+customerPrice+'&ino='+invoceNo, false);
          req.send();
          //setTimeout(function(){window.location.reload();},100);
          if(req.status == 200) {  
            if (is_empty(req.responseText)) alert("Insert error!!!");
            else {
              alert("Successfully added stock " + req.responseText);
              tbl = document.getElementById("stock_table");
              if (is_empty(String(tbl.innerHTML).trim())) tbl.innerHTML += " <tr><td>NumberOf</td><td>Delivery Price</td><td>Customer Price</td><td>Invoice</td></tr> ";
              tbl.innerHTML += " <tr><td>" + numberOfItems + "</td><td>" + deliveryPrice + "</td><td>" + customerPrice + "</td><td>" + invoceNo + "</td></tr> ";              
            }
          }
          window.location.href = "#tab1";
        }
        function select_item(id) {
          req = new XMLHttpRequest();
          req.open("GET", "/select_item?id="+id);
          req.send();
          //window.location.reload();
          setTimeout(function(){window.location.reload();},100);
        }
        function report_all_items() {
          req = new XMLHttpRequest();
          req.open("GET", "/report_all_items");
          req.send();
        }
        function load_item_names() {
          dlist = document.getElementById("item_names");
          if (!is_empty(String(dlist.innerHTML).trim())) return;
          req = new XMLHttpRequest();
          req.open("GET", "/item_names", false);
          req.send();
          if(req.status == 200) {  
            res = req.responseText.split("|");
            option = "";
            for (i = 0; i < res.length; i ++) option += " <option value='" + res[i] + "' /> ";
            dlist.innerHTML = option;
          }
        }
        function load_item_sizes() {
          dlist = document.getElementById("item_sizes");
          if (!is_empty(String(dlist.innerHTML).trim())) return;
          req = new XMLHttpRequest();
          req.open("GET", "/item_sizes", false);
          req.send();
          if(req.status == 200) {  
            res = req.responseText.split("|");
            option = "";
            for (i = 0; i < res.length; i ++) option += " <option value='" + res[i] + "' /> ";
            dlist.innerHTML = option;
          }
        }
        function load_item_providers() {
          dlist = document.getElementById("item_providers");
          if (!is_empty(String(dlist.innerHTML).trim())) return;
          req = new XMLHttpRequest();
          req.open("GET", "/item_providers", false);
          req.send();
          if(req.status == 200) {  
            res = req.responseText.split("|");
            option = "";
            for (i = 0; i < res.length; i ++) option += " <option value='" + res[i] + "' /> ";
            dlist.innerHTML = option;
          }
        }
        function report_filtered_item() {
          itemNo = document.getElementById("rep-item-no").value;
          itemName = document.getElementById("rep-item-name").value;
          itemSize = document.getElementById("rep-item-size").value;
          itemProvider = document.getElementById("rep-item-provider").value;
          itemDate = document.getElementById("rep-item-dt").value;
          window.location.href = "/report_filtered_item?no="+itemNo+'&name='+itemName+'&size='+itemSize+'&provider='+itemProvider+'&dt='+itemDate;
        }
        function report_filtered_sell() {
          itemNo = document.getElementById("rep-sell-no").value;
          itemName = document.getElementById("rep-sell-name").value;
          itemSize = document.getElementById("rep-sell-size").value;
          itemProvider = document.getElementById("rep-sell-provider").value;
          itemDate = document.getElementById("rep-sell-dt").value;          
          window.location.href = "/report_filtered_sell?no="+itemNo+'&name='+itemName+'&size='+itemSize+'&provider='+itemProvider+'&dt='+itemDate;
        }
        function report_filtered_stock() {
          itemNo = document.getElementById("rep-stock-no").value;
          itemName = document.getElementById("rep-stock-name").value;
          itemSize = document.getElementById("rep-stock-size").value;
          itemProvider = document.getElementById("rep-stock-provider").value;
          itemDate = document.getElementById("rep-stock-dt").value;          
          window.location.href = "/report_filtered_stock?no="+itemNo+'&name='+itemName+'&size='+itemSize+'&provider='+itemProvider+'&dt='+itemDate;
        }    
        function delete_filtered_item() {
          itemNo = document.getElementById("del-item-no").value;
          itemName = document.getElementById("del-item-name").value;
          itemSize = document.getElementById("del-item-size").value;
          itemProvider = document.getElementById("del-item-provider").value;
          itemDate = document.getElementById("del-item-dt").value;          
          window.location.href = "/delete_filtered_item?no="+itemNo+'&name='+itemName+'&size='+itemSize+'&provider='+itemProvider+'&dt='+itemDate;
        }    
        function delete_filtered_stock() {
          itemNo = document.getElementById("del-item-no").value;
          itemName = document.getElementById("del-item-name").value;
          itemSize = document.getElementById("del-item-size").value;
          itemProvider = document.getElementById("del-item-provider").value;
          itemDate = document.getElementById("del-item-dt").value;          
          window.location.href = "/delete_filtered_stock?no="+itemNo+'&name='+itemName+'&size='+itemSize+'&provider='+itemProvider+'&dt='+itemDate;
        }    
        function delete_filtered_sell() {
          itemNo = document.getElementById("del-item-no").value;
          itemName = document.getElementById("del-item-name").value;
          itemSize = document.getElementById("del-item-size").value;
          itemProvider = document.getElementById("del-item-provider").value;
          itemDate = document.getElementById("del-item-dt").value;          
          window.location.href = "/delete_filtered_sell?no="+itemNo+'&name='+itemName+'&size='+itemSize+'&provider='+itemProvider+'&dt='+itemDate;
        }           
        function showTab(el) {
          ul = el.parentNode.parentNode;
          li = ul.getElementsByTagName("li");
          n = li.length;
          idbase = ul.getAttribute("id");
          for (i=0; i<n; i++) {
            sel = (li[i] == el.parentNode);
            e = document.getElementById(idbase+i);
            if (e != null) {
              e.setAttribute("class", sel ? "shown" : "hidden");
            }
            if (sel) {
              li[i].firstChild.setAttribute("class", "selected");
            } else {
              li[i].firstChild.removeAttribute("class");
            }
          }
        }
        </script>
        <style type="text/css">
        body { font-family: 'Times New Roman'; }
        .oinfo { position:absolute; z-index:1; top:0; right:1em;}
        .ocontrol { position:absolute; z-index:2; top:0; left:1em; }
        .onoff { font-family:monospace; font-weight:bold; width:2em; display:inline-block; }
        .on { color:green; }
        .off { color:red; }
        .noffo { color:gray; }
        .section { font-weight:bold; }
        .tabs { 
          background:#888;
          color:#111;
          //padding:15px 20px;
          //width:800px;
          border:1px solid #222;
          margin:4px auto;
        }
        .tabs li { list-style:none; float:left; }
        .tabs ul a {
          display:block;
          padding:6px 10px;
          text-decoration:none!important;
          margin:1px;
          margin-left:0;
          //font:10px Verdana;
          color:#FFF;
          background:#444;
        }
        .tabs ul a:hover {
          color:#FFF;
          background:#111;
          }
        .tabs ul a.selected {
          margin-bottom:0;
          color:#000;
          background:snow;
          border-bottom:1px solid snow;
          cursor:default;
          }
        .tabs div {
          padding:0px 10px 8px 10px;
          *padding-top:3px;
          *margin-top:-15px;
          clear:left;
          background:snow;
        }
        .hidden { display: none; }
        .shown { display: block; }
        .ct { 
          background:#888 !important;
          color:#111;
          padding:15px 20px;
          border:1px solid #222;
          margin:4px auto;
        }
        .ct li { list-style:none; float:left; }
        .ct ul a {
          display:block;
          padding:6px 10px;
          text-decoration:none!important;
          margin:1px;
          margin-left:0;
          color:#FFF;
          background:#444;
        }
        .ct ul a:hover {
          color:#FFF;
          background:#111;
          }
        .ct ul a.selected {
          margin-bottom:0;
          color:#000;
          background:snow;
          border-bottom:1px solid snow;
          cursor:default;
          }
        .ct div {
          padding:10px 10px 8px 10px;
          *padding-top:3px;
          *margin-top:-15px;
          clear:left;
          background:snow;
        }
        .ctul { }
        .cts {
          //min-height:10pc;
        }
        ul { padding-left: 1em; }
        #tab0 { padding-top: 1px; }
        .title {
          float:right;
          font-size:16pt;
          font-weight:bold;
          text-shadow: white 0 0 5px;
          padding-right:1ex;
        }
        .bc-item {
          display:inline-block;
          width:3em;
          text-align:right;
        }
        .bc-left {
          display:inline-block;
          vertical-align:top;
        }
        .bc-left-vr {
          display:inline-block;
          border-left:1px solid black;
        }
        .info-can-set {
          background-color:#eeeeee;
        }
        </style>
        </head>
        <body>
    ''')

def writeMainPageSuffix(key, f, item_id, stock_id):
  
    bShowTab1 = False
    mo = re.match(".*?\?g_stock_id=(.*?)&g_item_id=(.*?)$",key)    
    if 0 == item_id:
        try:
            item_id = int(str(mo.group(2)))
        except Exception as e:
            item_id = 0
        if 0 != item_id:
            rows = dbExec('SELECT nn_stock_id FROM nn_stock WHERE nn_stock_item_id = ' + str(item_id), 0, 1)
            if rows != []:
                stock_id = rows[0][0]
            if 0 != stock_id:
                 bShowTab1 = True
    else:
        try:
            bShowTab1 = ( (int(str(mo.group(1))) > 0) and (0 == int(str(mo.group(2)))) )
        except Exception as e:
                None
    # main tabs
    f.write('<div class="tabs">\n')
    f.write('<ul id="tab"><li><a href="#tab0" ' + ('class="selected"' if not bShowTab1 else '') + ' onclick="showTab(this)">Sell</a></li><li><a href="#tab1" ' + ('class="selected"' if bShowTab1 else '') + ' onclick="showTab(this)">Stock</a></li><li><a href="#tab2" onclick="showTab(this)">Item</a></li><li><a href="#tab3" onclick="showTab(this)">Reports</a></li><li><a href="#tab4" onclick="showTab(this)">CleanUp</a></li></ul>\n')
    f.write('<span class="title">Microshop</span>\n')

    #sells
    f.write('<div id="tab0" class="' + ('shown' if not bShowTab1 else 'hidden') + '">\n<center>\n')
    f.write('<div><form><br>')
    f.write(' <input type="hidden" id="g_stock_id" value="' + str(stock_id) + '">')
    f.write(' NumberOf <input id="number-of-items" type="text" value="0" maxlength="4" size="4em"> , ')        
    f.write(' <input type="button" onclick="add_sell()" value="Sell" ' + ('disabled' if stock_id == 0 else '') + ' /> , ')
    f.write(' <input id="search-text-sell" type="text" size="20em"/> <a href="#tab0" onclick="search_by_text()">Filter</a><br>')
    f.write('</form></div>')
        
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th>No<td>Name<td>Size<td>NumberOf<td>Price<td>Provider<td>Invoice<td>Date</th>\n')
    rows = dbExec('SELECT s.nn_stock_id, i.nn_item_no, i.nn_item_name, i.nn_item_size, s.nn_stock_number_of_items, s.nn_stock_customer_price, i.nn_item_provider, s.nn_stock_invoice_no, s.nn_stock_delivery_dt FROM nn_item as i, nn_stock as s WHERE i.nn_item_id = s.nn_stock_item_id and s.nn_stock_number_of_items > 0', dbStockOffset(stock_id, False), g_maxRows)
    for row in rows:
        f.write('<tr style="' + ('font-weight:bold' if stock_id == row[0] else 'background-color:grey') + '" id=' + str(row[1]) + '><td>' + unquote(str(row[1])) + '<td><a href="/?g_stock_id=' + str(row[0]) + '" >' + unquote(str(row[2])) + '</a><td>' + unquote(str(row[3])) + '<td>' + str(row[4]) + '<td>' + str(row[5]/100.0) + '<td>' + unquote(str(row[6])) + '<td>' + unquote(str(row[7])) + '<td>' + str(row[8]) + '</tr>\n')
    f.write('</table>\n')
        
    f.write('</div>\n')

    #stock
    f.write('<div id="tab1" class="' + ('shown' if bShowTab1 else 'hidden') + '">\n<center>\n')
    f.write('<div><form><br>')
    f.write(' <input type="hidden" id="g_stock_id" value="' + str(stock_id) + '">')    
    f.write(' NumberOf <input id="num-items" type="text" value="0" maxlength="4" size="4em"> , ')
    f.write(' Delivery Price <input id="delivery-price" type="text" value="00.00" maxlength="7" size="8em"> , ')
    f.write(' Customer Price <input id="customer-price" type="text" value="00.00" maxlength="7" size="8em"> , ')
    f.write(' Invoice <input id="invoice-no" type="text" size="10em"> , ')        
    f.write(' <input type="button" onclick="add_stock()" value="Add" ' + ('disabled' if stock_id == 0 else '') + ' /> , ')
    f.write(' <input id="search-text-stock" type="text" size="20em"/> <a href="#tab1" onclick="search_by_text_with_empty_positions()">Filter</a><br>')
    f.write(' <br> <table border=1 id="stock_table" > </table> ')    
    f.write('</form></div>')

    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th>No<td>Name<td>Size<td>Provider</th>\n')
    rows = dbExec('SELECT nn_item_id, nn_item_no, nn_item_name, nn_item_size, nn_item_provider FROM nn_item', dbItemOffset(item_id), g_maxRows)
    for row in rows:
        f.write('<tr style="' + ('font-weight:bold' if item_id == row[0] else 'background-color:grey') + '" id=' + str(row[0]) + '><td>' + unquote(str(row[1])) + '<td><a href="/?g_stock_id=0&g_item_id=' + str(row[0]) + '" >' + unquote(str(row[2])) + '</a><td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '</tr>\n')
    f.write('</table>\n')

    f.write('</div>\n')

    #items
    f.write('<div id="tab2" class="hidden">\n<center>\n')
    f.write('<div><form><br>')
    f.write(' No <input id="item-no" type="text" size="10em"> , ')
    f.write(' Name <input id="item-name" type="text" list=item_names onclick="load_item_names()" size="40em"> <datalist id="item_names"> </datalist> , ')
    f.write(' Size <input id="item-size" type="text" list=item_sizes onclick="load_item_sizes()" size="4em"> <datalist id="item_sizes"> </datalist> , ')
    f.write(' Provider <input id="item-provider" type="text" list=item_providers onclick="load_item_providers()" size="40em"> <datalist id="item_providers"> </datalist> ')
    f.write(' <input type="button" onclick="add_item()" value="Add"/><br>')
    f.write(' <br> <table border=1 id="item_table" > </table> ')
    f.write('</form></div>')
    f.write('</div>\n')

    #remove
    f.write('<div id="tab4" class="hidden">\n<center>\n')
    f.write('<div><form><br>')
    f.write('<a href="/remove_zero_items">Remove zero items</a> (sells also will be removed)<br>')
    f.write('<a href="/form_remove_item">Remove items</a><br>')
    f.write('<a href="/form_remove_stock">Removed deliveries (stock)</a><br>')
    f.write('<a href="/form_remove_sell">Remove sells</a><br>')
    f.write('<br><div><form>')
    f.write(' No <input id="del-item-no" type="text" size="10em"> , ')
    f.write(' Name <input id="del-item-name" type="text" size="40em"> , ')
    f.write(' Size <input id="del-item-size" type="text" size="4em"> , ')
    f.write(' Provider <input id="del-item-provider" type="text" size="40em"> , ')
    f.write(' Date <input id="del-item-dt" type="text" size="10em"> Look for ')    
    f.write(' <input type="button" onclick="delete_filtered_item()" value="Item"/> ')
    f.write(' <input type="button" onclick="delete_filtered_stock()" value="Stock"/> ')
    f.write(' <input type="button" onclick="delete_filtered_sell()" value="Sell"/> ')
    f.write('</form></div>')    
    f.write('</form></div>')
    f.write('</div>\n')

    #reports
    f.write('<div id="tab3" class="hidden">\n<center>\n')
    f.write('''<div class="ct"><ul id="ct" class="ctul"><li><a onclick="showTab(this)" href="#ct0" class="selected"><i>About</i></a></li><li><a onclick="showTab(this)" href="#ct1">Item</a></li><li><a onclick="showTab(this)" href="#ct2">Stock</a></li><li><a onclick="showTab(this)" href="#ct3">Sell</a></li></ul>''')       
    f.write('<div class="cts">')
        
    # version report
    f.write('<div id="ct0" class="show">')
    rows = dbExec('select * from nn_version')
    for row in rows:
        f.write('<b>' + g_title + '</b>')
        f.write('<br>Version: ')
        f.write(row[0])
    f.write('</div>')

    # item report
    f.write('<div id="ct1" class="hidden">')
    f.write('<a href="/report_all_items">All items</a><br>')
    f.write('<a href="/report_items_by_providers">Items by Providers</a><br>')
    f.write('<a href="/report_items_by_size">Items by Sizes</a><br>')
    f.write('<div><form>')    
    f.write(' No <input id="rep-item-no" type="text" size="10em"> , ')
    f.write(' Name <input id="rep-item-name" type="text" size="40em"> , ')
    f.write(' Size <input id="rep-item-size" type="text" size="4em"> , ')
    f.write(' Provider <input id="rep-item-provider" type="text" size="40em"> , ')
    f.write(' Date <input id="rep-item-dt" type="text" size="10em"> ')
    f.write(' <input type="button" onclick="report_filtered_item()" value="Filter"/><br>')
    f.write('</form></div>')    
    f.write('</div>')        

    # stock report
    f.write('<div id="ct2" class="hidden">')
    f.write('<a href="/report_all_stock">All Stock</a><br>')
    f.write('<a href="/report_stock_by_item">Stock by Items</a><br>')
    f.write('<div><form>')    
    f.write(' No <input id="rep-stock-no" type="text" size="10em"> , ')
    f.write(' Name <input id="rep-stock-name" type="text" size="40em"> , ')
    f.write(' Size <input id="rep-stock-size" type="text" size="4em"> , ')
    f.write(' Provider <input id="rep-stock-provider" type="text" size="40em"> , ')
    f.write(' Date <input id="rep-stock-dt" type="text" size="10em"> ')    
    f.write(' <input type="button" onclick="report_filtered_stock()" value="Filter"/><br>')
    f.write('</form></div>')    
    f.write('</div>')

    # sell report
    f.write('<div id="ct3" class="hidden">')
    f.write('<a href="/report_all_sells">All Sells</a><br>')
    f.write('<a href="/report_sells_by_date">Sells by Date</a><br>')
    f.write('<a href="/report_sells_by_providers">Sell By Providers</a> ( <a href="/report_sells_by_providers_compact">compact</a> )<br>')
    f.write('<a href="/report_sells_by_size">Sells by Sizes</a><br>')
    f.write('<div><form>')    
    f.write(' No <input id="rep-sell-no" type="text" size="10em"> , ')
    f.write(' Name <input id="rep-sell-name" type="text" size="40em"> , ')
    f.write(' Size <input id="rep-sell-size" type="text" size="4em"> , ')
    f.write(' Provider <input id="rep-sell-provider" type="text" size="40em"> , ')
    f.write(' Date <input id="rep-sell-dt" type="text" size="10em"> ')    
    f.write(' <input type="button" onclick="report_filtered_sell()" value="Filter"/><br>')
    f.write('</form></div>')       
    f.write('</div>')        

    f.write('</div>\n')        
    f.write('</div>\n')
    writePageSuffix(f)

def formRemoveItem(f):
    writePagePrefix(f, "Remove Items")
    f.write('''
        <script type="text/javascript">
        function remove_item(id) {
          req = new XMLHttpRequest();
          req.open("GET", "/remove_item?id="+id, false);
          req.send();
          if(req.status == 200) {  
            if (req.responseText == 'ok') alert("Successfully removed");
            else alert("Remove Error!!!");
          }
          setTimeout(function(){window.location.reload();},100);
        }
        </script>
    ''')
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">id<td>No<td>Name<td>Size<td>Provider<td>Date</th>\n')
    rows = dbExec('select * from nn_item')
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '<td><input type="button" onclick="remove_item(' + str(row[0]) + ')" value="Remove"/>' + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def formRemoveStock(f):
    writePagePrefix(f, "Remove Stock")
    f.write('''
        <script type="text/javascript">
        function remove_stock(id) {
          req = new XMLHttpRequest();
          req.open("GET", "/remove_stock?id="+id, false);
          req.send();
          if(req.status == 200) {  
            if (req.responseText == 'ok') alert("Successfully removed");
            else alert("Remove Error!!!");
          }
          setTimeout(function(){window.location.reload();},100);
        }
        </script>
    ''')
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')    
    f.write('<th id="machines-header">id<td>idItem<td>Number Of Items<td>Delivery Price<td>Customer Price<td>Delivery Date<td>Invoice No</th>\n')
    rows = dbExec('select * from nn_stock')
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '<td>' + unquote(str(row[6])) + '<td><input type="button" onclick="remove_stock(' + str(row[0]) + ')" value="Remove"/>' + '</tr>\n')
    f.write('</table>\n')       
    writePageSuffix(f)

def formRemoveSell(f):
    writePagePrefix(f, "Изтриване на Продажби")
    f.write('''
        <script type="text/javascript">
        function remove_sell(id) {
          req = new XMLHttpRequest();
          req.open("GET", "/remove_sell?id="+id, false);
          req.send();
          if(req.status == 200) {  
            if (req.responseText == 'ok') alert("Successfully removed");
            else alert("Remove Error!!!");
          }
          setTimeout(function(){window.location.reload();},100);
        }
        </script>
    ''')
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">id<td>idStock<td>Number Of Items<td>Date</th>\n')
    rows = dbExec('select * from nn_sell')
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + str(row[1]) + '<td>' + str(row[2]) + '<td>' + str(row[3]) + '<td><input type="button" onclick="remove_sell(' + str(row[0]) + ')" value="Remove"/>' + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def deleteFilteredItem(key, f):
    mo = re.match(".*?\?no=(.*?)&name=(.*?)&size=(.*?)&provider=(.*?)&dt=(.*?)$",key)
    stmt = "SELECT * FROM nn_item WHERE nn_item_id > 0 "
    if len(mo.group(1)) > 0:
        stmt += " and nn_item_no like \"%" + mo.group(1) + "%\""
    if len(mo.group(2)) > 0:
        stmt += " and nn_item_name like \"%" + mo.group(2) + "%\""
    if len(mo.group(3)) > 0:
        stmt += " and nn_item_size like \"%" + mo.group(3) + "%\""
    if len(mo.group(4)) > 0:
        stmt += " and nn_item_provider like \"%" + mo.group(4) + "%\""
    if len(mo.group(5)) > 0:
        stmt += " and nn_item_dt like \"%" + unquote(mo.group(5)) + "%\""        
    #print stmt
    rows = dbExec(stmt) 
    writePagePrefix(f, "Removed filtered items")
    f.write('''
        <script type="text/javascript">
        function remove_item(id) {
          req = new XMLHttpRequest();
          req.open("GET", "/remove_item?id="+id, false);
          req.send();
          if(req.status == 200) {  
            if (req.responseText == 'ok') alert("Successfully removed");
            else alert("Remove Error!!!");
          }
          setTimeout(function(){window.location.reload();},100);
        }
        </script>
    ''')   
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th>id<td>No<td>Name<td>Size<td>Provider<td>Date</th>\n')
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '<td><input type="button" onclick="remove_item(' + str(row[0]) + ')" value="Remove"/>' + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def deleteFilteredStock(key, f):
    mo = re.match(".*?\?no=(.*?)&name=(.*?)&size=(.*?)&provider=(.*?)&dt=(.*?)$",key)
    stmt = "SELECT s.nn_stock_id, i.nn_item_no, i.nn_item_name, i.nn_item_size, i.nn_item_provider,"
    stmt += " s.nn_stock_number_of_items, s.nn_stock_delivery_price, s.nn_stock_customer_price, s.nn_stock_invoice_no, s.nn_stock_delivery_dt"
    stmt += " FROM nn_item AS i, nn_stock AS s WHERE i.nn_item_id = s.nn_stock_item_id " 
    if len(mo.group(1)) > 0:
        stmt += " and i.nn_item_no like \"%" + mo.group(1) + "%\""
    if len(mo.group(2)) > 0:
        stmt += " and i.nn_item_name like \"%" + mo.group(2) + "%\""
    if len(mo.group(3)) > 0:
        stmt += " and i.nn_item_size like \"%" + mo.group(3) + "%\""
    if len(mo.group(4)) > 0:
        stmt += " and i.nn_item_provider like \"%" + mo.group(4) + "%\""
    if len(mo.group(5)) > 0:
        stmt += " and s.nn_stock_delivery_dt like \"%" + unquote(mo.group(5)) + "%\""
    #stmt += "ORDER BY i.nn_item_name"
    #print stmt
    rows = dbExec(stmt) 
    writePagePrefix(f, "Изтриване на Наличности")
    f.write('''
        <script type="text/javascript">
        function remove_stock(id) {
          req = new XMLHttpRequest();
          req.open("GET", "/remove_stock?id="+id, false);
          req.send();
          if(req.status == 200) {  
            if (req.responseText == 'ok') alert("Successfully removed");
            else alert("Remove Error!!!");
          }
          setTimeout(function(){window.location.reload();},100);
        }
        </script>
    ''')        
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th>id<td>No<td>Name<td>Size<td>Provider<td>NumberOf<td>Delivery Price<td>Customer Price<td>Invoice<td>Date</th>\n')
    for row in rows:
        f.write('<tr><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '<td>' + unquote(str(row[6]/100.0)) + '<td>' + unquote(str(row[7]/100.0)) + '<td>' + unquote(str(row[8])) + '<td>' + unquote(str(row[9])) + '<td><input type="button" onclick="remove_stock(' + str(row[0]) + ')" value="Remove"/>' + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def deleteFilteredSell(key, f):
    mo = re.match(".*?\?no=(.*?)&name=(.*?)&size=(.*?)&provider=(.*?)&dt=(.*?)$",key)
    stmt = "SELECT l.nn_sell_id, i.nn_item_no, i.nn_item_name, i.nn_item_size, i.nn_item_provider,"
    stmt += " l.nn_sell_number_of_items, s.nn_stock_customer_price, s.nn_stock_invoice_no, l.nn_sell_dt"
    stmt += " FROM nn_item AS i, nn_stock AS s, nn_sell AS l WHERE i.nn_item_id = s.nn_stock_item_id and s.nn_stock_id = l.nn_sell_stock_id " 
    if len(mo.group(1)) > 0:
        stmt += " and i.nn_item_no like \"%" + mo.group(1) + "%\""
    if len(mo.group(2)) > 0:
        stmt += " and i.nn_item_name like \"%" + mo.group(2) + "%\""
    if len(mo.group(3)) > 0:
        stmt += " and i.nn_item_size like \"%" + mo.group(3) + "%\""
    if len(mo.group(4)) > 0:
        stmt += " and i.nn_item_provider like \"%" + mo.group(4) + "%\""
    if len(mo.group(5)) > 0:
        stmt += " and l.nn_sell_dt like \"%" + unquote(mo.group(5)) + "%\""
    #print stmt
    rows = dbExec(stmt) 
    writePagePrefix(f, "Изтриване на Продажби")
    f.write('''
        <script type="text/javascript">
        function remove_sell(id) {
          req = new XMLHttpRequest();
          req.open("GET", "/remove_sell?id="+id, false);
          req.send();
          if(req.status == 200) {  
            if (req.responseText == 'ok') alert("Successfully removed");
            else alert("Remove Error!!!");
          }
          setTimeout(function(){window.location.reload();},100);
        }
        </script>
    ''')    
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th>id<td>No<td>Name<td>Size<td>Provider<td>NumberOf<td>Price<td>Invoice<td>Date</th>\n')
    for row in rows:
        f.write('<tr><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '<td>' + unquote(str(row[6]/100.0)) + '<td>' + unquote(str(row[7])) + '<td>' + unquote(str(row[8])) + '<td><input type="button" onclick="remove_sell(' + str(row[0]) + ')" value="Remove"/>' + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def reportItemsAll(f):
    writePagePrefix(f, "Items")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">id<td>No<td>Name<td>Size<td>Provider<td>Date</th>\n')
    rows = dbExec('select * from nn_item')
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def reportItemsByProviders(f):
    writePagePrefix(f, "Items by Providers")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">id<td>No<td>Name<td>Size<td>Provider<td>Date</th>\n')
    rows = dbExec('select * from nn_item order by nn_item_provider, nn_item_no')        
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def reportItemsBySize(f):
    writePagePrefix(f, "Item by Sizes")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">id<td>No<td>Name<td>Size<td>Provider<td>Date</th>\n')
    rows = dbExec('select * from nn_item order by nn_item_size, nn_item_no')        
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def reportFilteredItem(key, f):
    mo = re.match(".*?\?no=(.*?)&name=(.*?)&size=(.*?)&provider=(.*?)&dt=(.*?)$",key)
    stmt = "SELECT * FROM nn_item WHERE nn_item_id > 0 "
    if len(mo.group(1)) > 0:
        stmt += " and nn_item_no like \"%" + mo.group(1) + "%\""
    if len(mo.group(2)) > 0:
        stmt += " and nn_item_name like \"%" + mo.group(2) + "%\""
    if len(mo.group(3)) > 0:
        stmt += " and nn_item_size like \"%" + mo.group(3) + "%\""
    if len(mo.group(4)) > 0:
        stmt += " and nn_item_provider like \"%" + mo.group(4) + "%\""
    if len(mo.group(5)) > 0:
        stmt += " and nn_item_dt like \"%" + unquote(mo.group(5)) + "%\""
    #print stmt
    rows = dbExec(stmt) 
    writePagePrefix(f, "Items")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th>id<td>No<td>Name<td>Size<td>Provider<td>Date</th>\n')
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def reportStockAll(f):
    writePagePrefix(f, "Stock")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">id<td>idItem<td>Number Of Items<td>Delivery Price<td>Customer Price<td>Delivery Date<td>Invoice No</th>\n')
    rows = dbExec('select * from nn_stock')
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '<td>' + unquote(str(row[6])) + '</tr>\n')
    f.write('</table>\n')       
    writePageSuffix(f)

def reportStockByItem(f):
    writePagePrefix(f, "Stock by Items")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">No<td>Name<td>Size<td>Provider<td>NumberOf</th>\n')
    rows = dbExec('SELECT i.nn_item_no, i.nn_item_name, i.nn_item_size, i.nn_item_provider, s.nn_stock_number_of_items FROM nn_item AS i, nn_stock AS s WHERE s.nn_stock_item_id = i.nn_item_id order by i.nn_item_no')
    num = 0
    no = ''
    for row in rows:
        if no != '' and no != row[0]:
            f.write('<tr><td><td><td><td><td>' + str(num) + '</tr>\n')
            num = 0
        f.write('<tr><td>' + unquote(str(row[0])) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + str(row[4]) + '</tr>\n')
        no = row[0]
        num += row[4]
    f.write('<tr><td><td><td><td><td>' + str(num) + '</tr>\n')        
    f.write('</table>\n')       
    writePageSuffix(f)

def reportFilteredStock(key, f):
    mo = re.match(".*?\?no=(.*?)&name=(.*?)&size=(.*?)&provider=(.*?)&dt=(.*?)$",key)
    stmt = "SELECT s.nn_stock_id, i.nn_item_no, i.nn_item_name, i.nn_item_size, i.nn_item_provider,"
    stmt += " s.nn_stock_number_of_items, s.nn_stock_delivery_price, s.nn_stock_customer_price, s.nn_stock_invoice_no, s.nn_stock_delivery_dt"
    stmt += " FROM nn_item AS i, nn_stock AS s WHERE i.nn_item_id = s.nn_stock_item_id " 
    if len(mo.group(1)) > 0:
        stmt += " and i.nn_item_no like \"%" + mo.group(1) + "%\""
    if len(mo.group(2)) > 0:
        stmt += " and i.nn_item_name like \"%" + mo.group(2) + "%\""
    if len(mo.group(3)) > 0:
        stmt += " and i.nn_item_size like \"%" + mo.group(3) + "%\""
    if len(mo.group(4)) > 0:
        stmt += " and i.nn_item_provider like \"%" + mo.group(4) + "%\""
    if len(mo.group(5)) > 0:
        stmt += " and s.nn_stock_delivery_dt like \"%" + unquote(mo.group(5)) + "%\""
    #stmt += "ORDER BY i.nn_item_name"
    #print stmt
    rows = dbExec(stmt) 
    writePagePrefix(f, "Stock")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th>id<td>No<td>Name<td>Size<td>Provider<td>NumberOf<td>Delivery Price<td>Customer Price<td>Invoice<td>Date</th>\n')
    totalCP = 0
    totalDP = 0    
    for row in rows:
        totalDP += row[5] * row[6]
        totalCP += row[5] * row[7]        
        f.write('<tr><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '<td>' + unquote(str(row[6]/100.0)) + '<td>' + unquote(str(row[7]/100.0)) + '<td>' + unquote(str(row[8])) + '<td>' + unquote(str(row[9])) + '</tr>\n')
    f.write('<tr><td><td><td><td><td><td><td>' + unquote(str(totalDP/100.0)) + '<td>' + unquote(str(totalCP/100.0)) + '<td><td><td>' + str((totalCP - totalDP)/100.0) + '</tr>\n')        
    f.write('</table>\n')
    writePageSuffix(f)

def reportSellsByDate(f):
    writePagePrefix(f, "Sells by Date")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">No<td>Name<td>Size<td>NumberOf<td>Delivery Price<td>Customer Price<td>Date</th>\n')
    rows = dbExec('SELECT i.nn_item_no, i.nn_item_name, i.nn_item_size, l.nn_sell_number_of_items, s.nn_stock_delivery_price, s.nn_stock_customer_price, l.nn_sell_dt FROM nn_sell AS l, nn_item AS i, nn_stock AS s WHERE l.nn_sell_stock_id = s.nn_stock_id and s.nn_stock_item_id = i.nn_item_id order by l.nn_sell_dt')
    sumCP = 0
    sumDP = 0
    sumNum = 0    
    totalCP = 0
    totalDP = 0
    totalNum = 0    
    lastDt = ''
    for row in rows:
        if '' != lastDt and row[6][:len(lastDt)] != lastDt:
            f.write('<tr><td><td><td><td>' + str(sumNum) + '<td>' + str(sumDP/100.0) + '<td>' + str(sumCP/100.0) + '<td><td>' + str((sumCP - sumDP) / 100.0) + '</tr>\n')
            totalDP += sumDP
            sumDP = 0
            totalCP += sumCP
            sumCP = 0
            totalNum += sumNum
            sumNum = 0           
        f.write('<tr id=' + str(row[0]) + '><td>' + unquote(str(row[0])) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + str(row[3]) + '<td>' + str(row[4]/100.0) + '<td>' + str(row[5]/100.0) + '<td>' + str(row[6]) + '</tr>\n')
        lastDt = row[6][:10]
        sumDP += row[3] * row[4]
        sumCP += row[3] * row[5]
        sumNum += row[3]
    f.write('<tr><td><td><td><td>' + str(sumNum) + '<td>' + str(sumDP/100.0) + '<td>' + str(sumCP/100.0) + '<td><td>' + str((sumCP - sumDP) / 100.0) + '</tr>\n')
    totalDP += sumDP
    totalCP += sumCP
    totalNum += sumNum
    f.write('<tr style="font-weight:bold" ><td><td><td><td>' + str(totalNum) + '<td>' + str(totalDP/100.0) + '<td>' + str(totalCP/100.0) + '<td><td>' + str((totalCP - totalDP) / 100.0) + '</tr>\n')    
    f.write('</table>\n')
    writePageSuffix(f)

def reportSellsAll(f):
    writePagePrefix(f, "Sells")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">id<td>idStock<td>Number Of Items<td>Date</th>\n')
    rows = dbExec('select * from nn_sell')
    for row in rows:
        f.write('<tr id=' + str(row[0]) + '><td>' + str(row[0]) + '<td>' + str(row[1]) + '<td>' + str(row[2]) + '<td>' + str(row[3]) + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def reportSellsByProviders(f):
    writePagePrefix(f, "Sells by Providers")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">No<td>Name<td>Size<td>NumberOf<td>Delivery Price<td>Customer Price<td>Provider</th>\n')
    rows = dbExec('SELECT i.nn_item_no, i.nn_item_name, i.nn_item_size, l.nn_sell_number_of_items, s.nn_stock_delivery_price, s.nn_stock_customer_price, i.nn_item_provider FROM nn_sell AS l, nn_item AS i, nn_stock AS s WHERE l.nn_sell_stock_id = s.nn_stock_id and s.nn_stock_item_id = i.nn_item_id order by i.nn_item_provider')
    sumCP = 0
    sumDP = 0
    sumNum = 0
    totalCP = 0
    totalDP = 0
    totalNum = 0
    provider = ''
    for row in rows:
        if '' != provider and row[6] != provider:
            f.write('<tr><td><td><td><td>' + str(sumNum) + '<td>' + str(sumDP/100.0) + '<td>' + str(sumCP/100.0) + '<td><td>' + str((sumCP - sumDP) / 100.0) + '</tr>\n')
            totalDP += sumDP
            sumDP = 0
            totalCP += sumCP
            sumCP = 0
            totalNum += sumNum
            sumNum = 0
        f.write('<tr id=' + str(row[0]) + '><td>' + unquote(str(row[0])) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + str(row[3]) + '<td>' + str(row[4]/100.0) + '<td>' + str(row[5]/100.0) + '<td>' + str(row[6]) + '</tr>\n')
        provider = row[6]
        sumDP += row[3] * row[4]
        sumCP += row[3] * row[5]
        sumNum += row[3]
    f.write('<tr><td><td><td><td>' + str(sumNum) + '<td>' + str(sumDP/100.0) + '<td>' + str(sumCP/100.0) + '<td><td>' + str((sumCP - sumDP) / 100.0) + '</tr>\n')
    totalDP += sumDP
    totalCP += sumCP
    totalNum += sumNum
    f.write('<tr style="font-weight:bold" ><td><td><td><td>' + str(totalNum) + '<td>' + str(totalDP/100.0) + '<td>' + str(totalCP/100.0) + '<td><td>' + str((totalCP - totalDP) / 100.0) + '</tr>\n')
    f.write('</table>\n')
    writePageSuffix(f)

def reportFilteredSell(key, f):
    mo = re.match(".*?\?no=(.*?)&name=(.*?)&size=(.*?)&provider=(.*?)&dt=(.*?)$",key)
    stmt = "SELECT l.nn_sell_id, i.nn_item_no, i.nn_item_name, i.nn_item_size, i.nn_item_provider,"
    stmt += " l.nn_sell_number_of_items, s.nn_stock_customer_price, s.nn_stock_invoice_no, l.nn_sell_dt"
    stmt += " FROM nn_item AS i, nn_stock AS s, nn_sell AS l WHERE i.nn_item_id = s.nn_stock_item_id and s.nn_stock_id = l.nn_sell_stock_id " 
    if len(mo.group(1)) > 0:
        stmt += " and i.nn_item_no like \"%" + mo.group(1) + "%\""
    if len(mo.group(2)) > 0:
        stmt += " and i.nn_item_name like \"%" + mo.group(2) + "%\""
    if len(mo.group(3)) > 0:
        stmt += " and i.nn_item_size like \"%" + mo.group(3) + "%\""
    if len(mo.group(4)) > 0:
        stmt += " and i.nn_item_provider like \"%" + mo.group(4) + "%\""
    if len(mo.group(5)) > 0:
        stmt += " and l.nn_sell_dt like \"%" + unquote(mo.group(5)) + "%\""
    #stmt += "ORDER BY i.nn_item_name"
    #print stmt
    rows = dbExec(stmt) 
    writePagePrefix(f, "Sells")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th>id<td>No<td>Name<td>Size<td>Provider<td>NumberOf<td>Price<td>Invoice<td>Date</th>\n')
    totalCP = 0
    for row in rows:
        totalCP += row[5] * row[6]
        f.write('<tr><td>' + str(row[0]) + '<td>' + unquote(str(row[1])) + '<td>' + unquote(str(row[2])) + '<td>' + unquote(str(row[3])) + '<td>' + unquote(str(row[4])) + '<td>' + unquote(str(row[5])) + '<td>' + unquote(str(row[6]/100.0)) + '<td>' + unquote(str(row[7])) + '<td>' + unquote(str(row[8])) + '</tr>\n')
    f.write('<tr><td><td><td><td><td><td><td>' + unquote(str(totalCP/100.0)) + '<td><td></tr>\n')        
    f.write('</table>\n')
    writePageSuffix(f)

def reportSellsByProvidersCompact(f):
    writePagePrefix(f, "Sells by Providers (compact)")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">Provider<td>NumberOf<td>Delivery Price<td>Customer Price</th>\n')
    rows = dbExec('SELECT i.nn_item_provider, sum(l.nn_sell_number_of_items), s.nn_stock_delivery_price, s.nn_stock_customer_price FROM nn_sell AS l, nn_item AS i, nn_stock AS s WHERE l.nn_sell_stock_id = s.nn_stock_id and s.nn_stock_item_id = i.nn_item_id group by i.nn_item_provider, s.nn_stock_delivery_price, s.nn_stock_customer_price')
    totalDP = 0
    totalCP = 0
    totalNum = 0
    totalVal = 0
    strData = ' var data = ['
    for row in rows:
        dp = row[1] * row[2]
        cp = row[1] * row[3]
        val = cp - dp
        color = "rgb(%d, %d, %d)" %  (random.randint(1,255), random.randint(1,255), random.randint(1,255))
        strData += ' { value: %d, color:"%s" }, ' %  (val, color)
        f.write('<tr><td>' + unquote(str(row[0])) + '<td>' + str(row[1]) + '<td>' + str(dp / 100.0) + '<td>' + str(cp / 100.0) + '<td  style="background:' + color + '" >' + str(val / 100.0) + '</tr>\n')
        totalDP += dp
        totalCP += cp
        totalNum += row[1]
        totalVal += val
    f.write('<tr><td><td>' + str(totalNum) + '<td>' + str(totalDP / 100.0) + '<td>' + str(totalCP / 100.0) + '<td>' + str(totalVal / 100.0) + '</tr>\n')
    f.write('</table>\n')    
    writePageSuffix(f)

def reportSellsBySize(f):
    writePagePrefix(f, "Sells by Sizes")
    f.write('<table border=1 cellpadding=5 cellspacing=0 id="machines">\n')
    f.write('<th id="machines-header">Size<td>NumberOf<td>Delivery Price<td>Customer Price</th>\n')
    rows = dbExec('SELECT i.nn_item_size, sum(l.nn_sell_number_of_items), s.nn_stock_delivery_price, s.nn_stock_customer_price FROM nn_sell AS l, nn_item AS i, nn_stock AS s WHERE l.nn_sell_stock_id = s.nn_stock_id and s.nn_stock_item_id = i.nn_item_id group by i.nn_item_size, s.nn_stock_delivery_price, s.nn_stock_customer_price')
    totalDP = 0
    totalCP = 0
    totalNum = 0
    totalVal = 0
    labels = []
    vals = []
    for row in rows:
        dp = row[1] * row[2]
        cp = row[1] * row[3]
        val = cp - dp
        f.write('<tr><td>' + unquote(str(row[0])) + '<td>' + str(row[1]) + '<td>' + str(dp / 100.0) + '<td>' + str(cp / 100.0) + '<td>' + str(val / 100.0) + '</tr>\n')
        totalDP += dp
        totalCP += cp
        totalNum += row[1]
        totalVal += val
        vals = vals + [val/100.0]
        labels = labels + [unquote(str(row[0]))]
    f.write('<tr><td><td>' + str(totalNum) + '<td>' + str(totalDP / 100.0) + '<td>' + str(totalCP / 100.0) + '<td>' + str(totalVal / 100.0) + '</tr>\n')
    f.write('</table>\n')    
    writePageSuffix(f)

def parseKeyToEnv(key):
    stock_id = 0
    mo = re.match(".*?\?g_stock_id=(.*?)$",key)
    try:
        stock_id = int(str(mo.group(1)))
    except Exception as e:
        stock_id = 0
    if 0 == stock_id:
        mo = re.match(".*?\?g_stock_id=(.*?)&",key)
        try:
            stock_id = int(str(mo.group(1)))
        except Exception as e:
            stock_id = 0
    rows = dbExec('SELECT i.nn_item_id, i.nn_item_no, i.nn_item_name, i.nn_item_size, s.nn_stock_customer_price FROM nn_item AS i, nn_stock AS s WHERE i.nn_item_id = s.nn_stock_item_id and s.nn_stock_id = ' + str(stock_id))
    if rows == []:
        stock_id = 0
        item_id = 0
    else:
        item_id = rows[0][0]
    return [item_id, stock_id]
  
def writeResponse(key, f):
    [item_id, stock_id] = parseKeyToEnv(key)
    if key == '/' or key[:3] == '/?g':
        writeMainPagePrefix(f)
        writeMainPageSuffix(key, f, item_id, stock_id)                
    elif key == '/toggle':
        print "toggle"
    elif key == '/icon.png':
        f.write('')
    elif key[:len('/add_item?')] == '/add_item?':
        mo = re.match(".*?\?no=(.*?)&name=(.*?)&size=(.*?)&provider=(.*?)$",key)        
        rows = dbExec("SELECT * FROM nn_item WHERE nn_item_no = \"" + mo.group(1) + "\" and nn_item_size = \"" + mo.group(3) + "\"")
        if rows != []:
            return
        trans = 'BEGIN TRANSACTION;\n'
        trans += '''INSERT INTO nn_item (nn_item_no, nn_item_name, nn_item_size, nn_item_provider, nn_item_dt) VALUES ("''' + mo.group(1) + '''", "''' + mo.group(2) + '''", "''' + mo.group(3) + '''", "''' + mo.group(4) + '''", datetime('now'));'''
        trans += "INSERT INTO nn_stock (nn_stock_item_id, nn_stock_number_of_items, nn_stock_delivery_price, nn_stock_customer_price, nn_stock_invoice_no, nn_stock_delivery_dt) VALUES ( (select nn_item_id from nn_item where nn_item_no = '" + mo.group(1) + "'), 0, 0, 0, 0, datetime('now'));"
        trans += 'COMMIT;'
        dbExec(trans)
        rows = dbExec("SELECT MAX(nn_item_id) FROM nn_item")
        if rows != []:
            f.write(str(rows[0][0]))
    elif key[:len('/add_sell?')] == '/add_sell?':
        #print key
        mo = re.match(".*?\?g_stock_id=(.*?)&number=(.*?)$",key)
        if 0 == stock_id:
            return
        rows = dbExec("SELECT nn_stock_number_of_items FROM nn_stock WHERE nn_stock_id=" + str(stock_id))
        try:
            if int(mo.group(2)) == 0:
                return
            if int(mo.group(2)) > rows[0][0]:
                return
        except Exception as e:
            return
        trans = 'BEGIN TRANSACTION;\n'
        trans += '''INSERT INTO nn_sell (nn_sell_stock_id, nn_sell_number_of_items, nn_sell_dt) VALUES (''' + str(stock_id) + ''', "''' + mo.group(2) + '''", datetime('now'));\n'''
        trans += "UPDATE nn_stock SET nn_stock_number_of_items = (nn_stock_number_of_items - " + mo.group(2) + ") WHERE nn_stock_id=" + str(stock_id) + ";\n"
        trans += 'COMMIT;'
        dbExec(trans)
        rows = dbExec("SELECT MAX(nn_sell_id) FROM nn_sell")
        if rows != []:
            f.write(str(rows[0][0]))        
    elif key[:len('/add_stock?')] == '/add_stock?':
        #print key
        mo = re.match(".*?\?g_stock_id=(.*?)&number=(.*?)&dprice=(.*?)&cprice=(.*?)&ino=(.*?)$",key)
        if 0 == item_id or 0 == stock_id:
            return
        trans = 'BEGIN TRANSACTION;\n'
        trans += '''INSERT INTO nn_stock (nn_stock_item_id, nn_stock_number_of_items, nn_stock_delivery_price, nn_stock_customer_price, nn_stock_invoice_no, nn_stock_delivery_dt) VALUES (''' + str(item_id) + ''', "''' + mo.group(2) + '''", "''' + str(float(mo.group(3)) * 100) + '''", "''' + str(float(mo.group(4)) * 100) + '''", "''' + mo.group(5) + '''", datetime('now'));'''
        trans += "DELETE FROM nn_stock WHERE nn_stock_number_of_items=0 and NOT EXISTS (SELECT 1 FROM nn_sell WHERE nn_sell_stock_id = nn_stock_id) and nn_stock_id=" + str(stock_id) + ";"
        trans += 'COMMIT;'
        dbExec(trans)
        rows = dbExec("SELECT MAX(nn_stock_id) FROM nn_stock")
        if rows != []:
            f.write(str(rows[0][0]))
    elif key[:len('/select_item?')] == '/select_item?':
        mo = re.match(".*?\?id=(.*?)$",key)
        stock_id = mo.group(1) # int(mo.group(1))
    elif key[:len('/search_by_text?')] == '/search_by_text?':
        #print key
        mo = re.match(".*?\?text=(.*?)$",key)
        like = mo.group(1)
        if '%' == like[:1]:
            like = re.escape(like)
        like = "%" + mo.group(1) + "%"
        rows = dbExec("SELECT s.nn_stock_id FROM nn_stock as s, nn_item as i WHERE s.nn_stock_item_id = i.nn_item_id and s.nn_stock_number_of_items > 0 and (i.nn_item_no like \"" + like + "\" or i.nn_item_name like \"" + like + "\")")
        if rows != []:
            stock_id = rows[0][0]
        #f.write('<html><meta http-equiv="refresh" content="0; url=http://example.com/" /></html>')
        f.write(str(stock_id))
    elif key[:len('/search_by_text_with_empty_positions?')] == '/search_by_text_with_empty_positions?':
        #print key
        mo = re.match(".*?\?text=(.*?)$",key)
        like = mo.group(1)
        if '%' == like[:1]:
            like = re.escape(like)
        like = "%" + mo.group(1) + "%"
        rows = dbExec("SELECT s.nn_stock_id FROM nn_stock as s, nn_item as i WHERE s.nn_stock_item_id = i.nn_item_id and (i.nn_item_no like \"" + like + "\" or i.nn_item_name like \"" + like + "\")")
        if rows != []:
            stock_id = rows[0][0]
        #f.write('<html><meta http-equiv="refresh" content="0; url=http://example.com/" /></html>')
        f.write(str(stock_id))
    elif key == '/remove_zero_items':
        rows = dbExec("SELECT i.nn_item_id FROM nn_item as i, nn_stock as s WHERE i.nn_item_id = s.nn_stock_item_id and s.nn_stock_number_of_items = 0")
        for row in rows:
            trans = 'BEGIN TRANSACTION;\n'
            trans += "DELETE FROM nn_item WHERE nn_item_id = " + str(row[0]) + ";\n"
            trans += "DELETE FROM nn_sell WHERE EXISTS (SELECT 1 FROM nn_stock WHERE nn_stock_id = nn_sell_stock_id and nn_stock_item_id = " + str(row[0]) + ");\n"            
            trans += "DELETE FROM nn_stock WHERE nn_stock_item_id = " + str(row[0]) + ";\n"
            trans += 'COMMIT;'
            dbExec(trans)
        writePagePrefix(f, "Изтриване")
        f.write('<b>OK</b>')
        writePageSuffix(f)
    elif key == '/item_names':
        rows = dbExec("SELECT DISTINCT nn_item_name FROM nn_item")
        response = ''
        for row in rows:
            response += unquote(str(row[0]))
            response += "|"
        f.write(response)            
    elif key == '/item_sizes':
        rows = dbExec("SELECT DISTINCT nn_item_size FROM nn_item")
        response = ''
        for row in rows:
            response += unquote(str(row[0]))
            response += "|"
        f.write(response)
    elif key == '/item_providers':
        rows = dbExec("SELECT DISTINCT nn_item_provider FROM nn_item")
        response = ''
        for row in rows:
            response += unquote(str(row[0]))
            response += "|"
        f.write(response)            
    elif key == '/form_remove_item':
        formRemoveItem(f)
    elif key[:len('/delete_filtered_item?')] == '/delete_filtered_item?':
        deleteFilteredItem(key, f)
    elif key == '/form_remove_stock':
        formRemoveStock(f)
    elif key[:len('/delete_filtered_stock?')] == '/delete_filtered_stock?':
        deleteFilteredStock(key, f)
    elif key == '/form_remove_sell':
        formRemoveSell(f)
    elif key[:len('/delete_filtered_sell?')] == '/delete_filtered_sell?':
        deleteFilteredSell(key, f)
    elif key[:len('/remove_item?')] == '/remove_item?':
        mo = re.match(".*?\?id=(.*?)$",key)
        if mo == None:
           return
        trans = 'BEGIN TRANSACTION;\n'
        trans += "DELETE FROM nn_item WHERE nn_item_id = " + mo.group(1) + ";\n"
        trans += "DELETE FROM nn_sell WHERE EXISTS (SELECT 1 FROM nn_stock WHERE nn_stock_id = nn_sell_stock_id and nn_stock_item_id = " + mo.group(1) + ");\n"
        trans += "DELETE FROM nn_stock WHERE nn_stock_item_id = " + mo.group(1) + ";\n"
        trans += 'COMMIT;'
        dbExec(trans)
        f.write('ok')
    elif key[:len('/remove_stock?')] == '/remove_stock?':
        mo = re.match(".*?\?id=(.*?)$",key)
        if mo == None:
           return
        trans = 'BEGIN TRANSACTION;\n'
        trans += "DELETE FROM nn_stock WHERE nn_stock_id = " + mo.group(1) + ";\n"
        trans += "DELETE FROM nn_sell WHERE nn_sell_stock_id = " + mo.group(1) + ";\n"
        trans += 'COMMIT;'
        dbExec(trans)
        f.write('ok')
    elif key[:len('/remove_sell?')] == '/remove_sell?':
        #print key
        mo = re.match(".*?\?id=(.*?)$",key)
        if mo == None:
           return
        dbExec("DELETE FROM nn_sell WHERE nn_sell_id = " + mo.group(1) + ";\n")
        f.write('ok')                    
    elif key == '/report_all_items':
        reportItemsAll(f)
    elif key == '/report_items_by_providers':
        reportItemsByProviders(f)
    elif key == '/report_items_by_size':
        reportItemsBySize(f)
    elif key[:len('/report_filtered_item?')] == '/report_filtered_item?':
        reportFilteredItem(key, f)
    elif key == '/report_all_sells':
        reportSellsAll(f)
    elif key == '/report_sells_by_date':        
        reportSellsByDate(f)
    elif key == '/report_sells_by_providers':
        reportSellsByProviders(f)
    elif key == '/report_sells_by_providers_compact':
        reportSellsByProvidersCompact(f)
    elif key == '/report_sells_by_size':
        reportSellsBySize(f)
    elif key[:len('/report_filtered_sell?')] == '/report_filtered_sell?':
        reportFilteredSell(key, f)        
    elif key == '/report_all_stock':
        reportStockAll(f)
    elif key == '/report_stock_by_item':
        reportStockByItem(f)
    elif key[:len('/report_filtered_stock?')] == '/report_filtered_stock?':
        reportFilteredStock(key, f)
    elif key == '/Chart.js':
        f.write(getChartJs())

def doNothing():
    None

def doTest(con):
    maxCount = 33
    for i in range(1,maxCount):
        stmt  = "INSERT INTO nn_item "
        stmt += "(nn_item_no, nn_item_name, nn_item_size, nn_item_provider, nn_item_dt) "
        stmt += "VALUES "
        stmt += "( 'no%d' , 'name%d' , 'size%d', 'provider%d', datetime('now'));" % (i,i,i,i)
        con.executescript(stmt)
        for j in range(1,maxCount):
            stmt  = "INSERT INTO nn_stock "
            stmt += "(nn_stock_item_id, nn_stock_number_of_items, nn_stock_delivery_price, nn_stock_customer_price, nn_stock_invoice_no, nn_stock_delivery_dt) "
            stmt += "VALUES "
            stmt += "( %d, 100 * %d , 100 * %d , 100 * (%d + 1), 'invoice%d', datetime('now'));" % (i,i,i,i,i)
            con.executescript(stmt)
            for k in range(1,maxCount):
                stmt  = "INSERT INTO nn_sell "
                stmt += "(nn_sell_stock_id, nn_sell_number_of_items, nn_sell_dt)"
                stmt += "VALUES "
                stmt += "( %d, %d, datetime('now'));" % (i * j,i)
                con.executescript(stmt)

#entry point
dbRestore()
g_con = lite.connect(g_dbFile)
dbVerify(g_con)
#doTest(g_con)
dbDump(g_con, time.strftime(g_dbPrefix + "%y%m%d") + '.sql')
g_server = HTTPServer(('', g_httpPort), MyHandler)
print "Listen on localhost:" + str(g_httpPort)
thread.start_new_thread(startServer, ())
while True:
    time.sleep(g_sleep)
    dbProcess(g_con)

#end of file
