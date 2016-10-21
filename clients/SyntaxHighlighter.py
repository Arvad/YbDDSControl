
'''
Python Syntax Highlighting Example

Copyright (C) 2009 Carson J. Q. Farmer

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public Licence as published by the Free Software
Foundation; either version 2 of the Licence, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public Licence for more
details.

You should have received a copy of the GNU General Public Licence along with
this program; if not, write to the Free Software Foundation, Inc., 51 Franklin
Street, Fifth Floor, Boston, MA  02110-1301, USA
'''

import sys
from PyQt4.QtGui import *
from PyQt4.QtCore import *

class MyHighlighter( QSyntaxHighlighter ):

    def __init__( self, parent, theme ):
      QSyntaxHighlighter.__init__( self, parent )
      self.parent = parent
      keyword = QTextCharFormat()
      modewords = QTextCharFormat()
      definings = QTextCharFormat()
      parametervaultvars = QTextCharFormat()
      steadystates = QTextCharFormat()
      loops = QTextCharFormat()
      comment = QTextCharFormat()
      channel = QTextCharFormat()

      self.highlightingRules = []

      # definings
      brush = QBrush( QColor('darkorange'), Qt.SolidPattern )
      pattern = QRegExp("^\s*[aA0-zZ9]+\s*=")
      definings.setForeground( brush )
      definings.setFontWeight( QFont.Black )
      rule = HighlightingRule( pattern, definings )
      self.highlightingRules.append( rule )

      # Channel
      pattern = QRegExp("^\s*[0-9aA-zZ]+:")
      channel.setForeground( QBrush(Qt.darkRed,Qt.SolidPattern))
      channel.setFontWeight (QFont.Bold)
      rule = HighlightingRule(pattern, channel)
      self.highlightingRules.append( rule )
      
      # Parameter Vault variables
      brush = QBrush( QColor('magenta'), Qt.SolidPattern )
      parametervaultvars.setForeground( brush )
      parametervaultvars.setFontWeight( QFont.Black )
      for word in ['A','B','C']:
        pattern = QRegExp( "\\b" + word + "\\b")
        rule = HighlightingRule( pattern, parametervaultvars )
        self.highlightingRules.append( rule )
            
      # steadystate
      pattern = QRegExp( "#steadystate|#endsteadystate" )
      steadystates.setForeground( QBrush(Qt.green) )
      steadystates.setFontWeight( QFont.Bold )
      rule = HighlightingRule( pattern, steadystates )
      self.highlightingRules.append( rule )

      # loops
      pattern = QRegExp( "#repeat|#endrepeat" )
      loops.setForeground( QBrush(Qt.red) )
      loops.setFontWeight( QFont.Bold )
      rule = HighlightingRule( pattern, loops )
      self.highlightingRules.append( rule )

      # keyword
      brush = QBrush( Qt.blue, Qt.SolidPattern )
      keyword.setForeground( brush )
      keyword.setFontWeight( QFont.Bold )
      keywords = QStringList( [ "freq", "at", "amp", "mode", "for",
                                "fromfreq", "fromamp","modfreq","modexcur"] )
      for word in keywords:
        pattern = QRegExp("\\b" + word + "\\b")
        pattern.setCaseSensitivity(False)
        rule = HighlightingRule( pattern, keyword )
        self.highlightingRules.append( rule )

      # modewords
      modewords.setForeground( QBrush( Qt.darkGreen, Qt.SolidPattern) )
      modewords.setFontWeight( QFont.Bold )
      keywords = QStringList( [ "Modulation", "Normal"] )
      for word in keywords:
        pattern = QRegExp("\\b" + word + "\\b")
        pattern.setCaseSensitivity(False)
        rule = HighlightingRule( pattern, modewords )
        self.highlightingRules.append( rule )

      # comment
      brush = QBrush( QColor('grey'), Qt.SolidPattern )
      pattern = QRegExp( "%[^\n]*" )
      comment.setForeground( brush )
      rule = HighlightingRule( pattern, comment )
      self.highlightingRules.append( rule )

    def highlightBlock( self, text ):
      for rule in self.highlightingRules:
        expression = QRegExp( rule.pattern )
        index = expression.indexIn( text )
        while index >= 0:
          length = expression.matchedLength()
          self.setFormat( index, length, rule.format )
          index = text.indexOf( expression, index + length )
      self.setCurrentBlockState( 0 )

class HighlightingRule():
  def __init__( self, pattern, format ):
    self.pattern = pattern
    self.format = format

class TestApp( QMainWindow ):
  def __init__(self):
    QMainWindow.__init__(self)
    font = QFont()
    font.setFamily( "Courier" )
    font.setFixedPitch( True )
    font.setPointSize( 10 )
    editor = QTextEdit()
    editor.setFont( font )
    editor.setReadOnly(True)
    try:
        with open('helpfile.html','r') as f:
            data = f.read()
            editor.setHtml(data)
    except Exception,e:
        print e
        editor.setPlainText('Sorry - "helpfile.txt" could not be found')
    #highlighter = MyHighlighter( editor, "Classic" )
    self.setCentralWidget( editor )
    self.setWindowTitle( "Syntax Highlighter" )


if __name__ == "__main__":
  app = QApplication( sys.argv )
  window = TestApp()
  window.show()
  sys.exit( app.exec_() )
