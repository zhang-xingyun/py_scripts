#!/bin/python
import MySQLdb

try:
   db = MySQLdb.connect("10.10.10.220", "athena", "", "athena", charset='utf8' )
except:
   print("Error: can not connect to db")
   exit(-1)

cursor = db.cursor()
sql="SELECT repo_url FROM athena.project where cr_complete=1 order by update_time desc"

try:
   cursor.execute(sql)
   results=cursor.fetchall()
   for row in results:
      url=row[0]
      print(url) 
except:
   print("Error: can not fetch data")

