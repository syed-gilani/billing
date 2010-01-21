from reportlab.platypus import BaseDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageTemplate, Frame, PageBreak, NextPageTemplate
from reportlab.platypus.flowables import UseUpSpace

from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.rl_config import defaultPageSize
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib import colors


from pprint import pprint

from reportlab.pdfgen import canvas
from reportlab.pdfgen.pathobject import PDFPathObject



# for font management
import os  
import reportlab  
from reportlab.pdfbase import pdfmetrics  
from reportlab.pdfbase.ttfonts import TTFont  
from reportlab.pdfgen.canvas import Canvas  
from reportlab.pdfbase.pdfmetrics import registerFontFamily


# for xml processing
import amara
from amara import bindery
from amara import xml_print


#
# for graphics
#
from pychartdir import *

#
#  Load Fonts
#
# add your font directories to the T1SearchPath in reportlab/rl_config.py as an alternative.
folder = os.path.dirname(reportlab.__file__) + os.sep + 'fonts'  


# register Vera (Included in reportlab)
pdfmetrics.registerFont(TTFont('Vera', os.path.join(folder, 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('VeraBd', os.path.join(folder, 'VeraBd.ttf')))
pdfmetrics.registerFont(TTFont('VeraIt', os.path.join(folder, 'VeraIt.ttf')))
pdfmetrics.registerFont(TTFont('VeraBI', os.path.join(folder, 'VeraBI.ttf')))
registerFontFamily('Vera',normal='Vera',bold='VeraBd',italic='VeraIt',boldItalic='VeraBI')

# register Verdana (MS Licensed CoreFonts http://sourceforge.net/projects/corefonts/files/)
pdfmetrics.registerFont(TTFont("Verdana", 'fonts/verdana.ttf'))  
pdfmetrics.registerFont(TTFont("VerdanaB", 'fonts/verdanab.ttf'))  
pdfmetrics.registerFont(TTFont("VerdanaI", 'fonts/verdanai.ttf'))  
registerFontFamily('Verdana',normal='Verdana',bold='VerdanaB',italic='VerdanaI')

# register Calibri (MS Licensed CoreFonts http://sourceforge.net/projects/corefonts/files/)
pdfmetrics.registerFont(TTFont("Courier", 'fonts/cour.ttf'))  
pdfmetrics.registerFont(TTFont("CourierB", 'fonts/courbd.ttf'))  
pdfmetrics.registerFont(TTFont("CourieI", 'fonts/couri.ttf'))  
pdfmetrics.registerFont(TTFont("CourieBI", 'fonts/courbi.ttf'))  
registerFontFamily('Courier',normal='Courier',bold='CourierB',italic='CourierBI')


#
# Globals
#
defaultPageSize = letter
PAGE_HEIGHT=letter[1]; PAGE_WIDTH=letter[0]
Title = "Skyline Bill"
pageinfo = "Skyline Bill"
firstPageName = 'FirstPage'
secondPageName = 'SecondPage'



class SIBillDocTemplate(BaseDocTemplate):
    """Structure Skyline Innovations Bill. """

    def build(self,flowables, canvasmaker=canvas.Canvas):
        """build the document using the flowables while drawing lines and figureson top of them."""
 
        BaseDocTemplate.build(self,flowables, canvasmaker=canvasmaker)
        
    def beforePage(self):
        print "Before Page: ", self.pageTemplate.id
        
    def afterPage(self):
        print "After Page"
        if self.pageTemplate.id == firstPageName:
            self.canv.saveState()
            self.canv.setStrokeColorRGB(0,255,128)
            self.canv.setLineWidth(.2)
            self.canv.setDash(1,3)
            self.canv.line(0,264,612,264)
            self.canv.line(0,528,612,528)
            self.canv.restoreState()
        
        
    def handle_pageBegin(self):
        print "handle_pageBegin"
        BaseDocTemplate.handle_pageBegin(self)






def progress(type,value):
    print type, value
     
def go():



    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BillLabel', fontName='Verdana', fontSize=10, leading=10))
    styles.add(ParagraphStyle(name='BillLabelRight', fontName='Verdana', fontSize=10, leading=10, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='BillLabelRight1', fontName='Verdana', fontSize=10, leading=10, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='BillLabelSm', fontName='Verdana', fontSize=8, leading=8))
    styles.add(ParagraphStyle(name='BillField', fontName='Courier', fontSize=10, leading=10, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='BillFieldRight', fontName='Courier', fontSize=10, leading=10, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='BillFieldLeft', fontName='Courier', fontSize=10, leading=10, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='BillFieldSm', fontName='Courier', fontSize=8, leading=10, alignment=TA_LEFT))
    style = styles['BillLabel']

    _showBoundaries = 0

    # 612w 792h

    #page one frames
    backgroundF = Frame(0,0, letter[0], letter[1], leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='background', showBoundary=_showBoundaries)

    # bill dates block
    billIssueDateF = Frame(78, 680, 120, 12, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billIssueDate', showBoundary=_showBoundaries)
    billDueDateF = Frame(203, 680, 140, 12, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, id='billDueDate', showBoundary=_showBoundaries)
    billPeriodTableF = Frame(78, 627, 265, 38, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=1, id='billPeriod', showBoundary=_showBoundaries)

    # summary charges block
    summaryChargesTableF = Frame(353, 627, 220, 62, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=7, id='summaryCharges', showBoundary=_showBoundaries)

    # balance block
    balanceF = Frame(78, 556, 265, 60, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='balance', showBoundary=_showBoundaries)

    # current charges block
    currentChargesF = Frame(353, 556, 220, 60, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='currentCharges', showBoundary=_showBoundaries)


    # graph one frame
    graphOne = Frame(30, 400, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphOne', showBoundary=_showBoundaries)
    
    # graph two frame
    graphTwo = Frame(310, 400, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphTwo', showBoundary=_showBoundaries)
    
    # graph three frame
    graphThree = Frame(30, 264, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphThree', showBoundary=_showBoundaries)
    
    # graph four frame
    graphFour = Frame(310, 264, 270, 127, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=2, id='graphOne', showBoundary=_showBoundaries)


    firstPage = PageTemplate(id=firstPageName,frames=[backgroundF, billIssueDateF, billDueDateF, billPeriodTableF, summaryChargesTableF, balanceF, currentChargesF, graphOne, graphTwo, graphThree, graphFour])


    # page two frames

    rbackgroundFrame = Frame(400,400, 100, 100, leftPadding=0, bottomPadding=0, rightPadding=0, topPadding=0, showBoundary=_showBoundaries)
    rcontentFrame = Frame(600,600, 100,100, leftPadding=10, bottomPadding=10, rightPadding=10, topPadding=10, showBoundary=_showBoundaries)

    secondPage = PageTemplate(id=secondPageName,frames=[backgroundF])

    doc = SIBillDocTemplate('bill.pdf', pagesize=letter, showBoundary=0, allowSplitting=0)
    doc.addPageTemplates([firstPage, secondPage])

    # Bind to XML bill
    dom = bindery.parse('../bills/Skyline-1-10001.xml')

    Elements = []

    #
    # First Page
    #

    # populate backgroundF
    image = Image('images/EmeraldCityBackground.png',letter[0], letter[1])
    Elements.append(image)


    # populate billIssueDateF
    Elements.append(Paragraph("<b>Issued</b> <font name='Courier'> " + str(dom.utilitybill.skylinebill.issued) + "</font>", styles['BillLabelRight']))
    Elements.append(UseUpSpace())

    # populate billDueDateF
    Elements.append(Paragraph("<b>Due Date</b> <font name='Courier'> " + str(dom.utilitybill.skylinebill.duedate) + "</font>", styles['BillLabelRight']))
    Elements.append(UseUpSpace())


    # populate billPeriodTableF
    serviceperiod = [
        [
            Paragraph(str(summary.service) + u' service period',styles['BillLabelSm']), 
            Paragraph(str(summary.billperiodbegin), styles['BillField']), 
            Paragraph(str(summary.billperiodend), styles['BillField'])
        ] 
        for summary in iter(dom.utilitybill.summary)
    ]

    t = Table(serviceperiod, [115,75,75])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'CENTER'), ('ALIGN',(2,0),(2,-1),'CENTER'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black) ]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate summaryChargesTableF
    utilitycharges = [
        [Paragraph("<b>Before Skyline</b>", styles['BillLabelRight']),Paragraph("<b>After Skyline</b>", styles['BillLabelRight'])]
    ]+[
        [Paragraph(str(summary.hypotheticalcharges),styles['BillFieldRight']), Paragraph(str(summary.currentcharges),styles['BillFieldRight'])]
        for summary in iter(dom.utilitybill.summary)
    ]

    t = Table(utilitycharges, [125,95])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (0,1), (-1,-1), 0.25, colors.black), ('BOX', (0,1), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate balances
    balances = [
        [Paragraph("<b>Prior Balance</b>", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.priorbalance),styles['BillFieldRight'])],
        [Paragraph("<b>Payment Received</b>", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.paymentreceived), styles['BillFieldRight'])],
        [Paragraph("<b>Balance Forward</b>", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.balanceforward), styles['BillFieldRight'])]
    ]

    t = Table(balances, [180,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    Elements.append(UseUpSpace())

    # populate current charges
    currentCharges = [
        [Paragraph("<b>Renewable Energy</b>", styles['BillLabelRight']), Paragraph(str(dom.utilitybill.skylinebill.skylinecharges), styles['BillFieldRight'])], 
        [Paragraph("<b>Current Charges</b>", styles['BillLabelRight']), Paragraph("not yet", styles['BillFieldRight'])],
        [Paragraph("<b>Total Due</b>", styles['BillLabelRight']), Paragraph("not yet", styles['BillFieldRight'])]
    ]

    t = Table(currentCharges, [135,85])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'RIGHT'), ('ALIGN',(1,0),(1,-1),'RIGHT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5), ('INNERGRID', (1,0), (-1,-1), 0.25, colors.black), ('BOX', (1,0), (-1,-1), 0.25, colors.black)]))
    Elements.append(t)
    Elements.append(UseUpSpace())


    # populate graph one

    # Construct period consumption/production ratio graph
    data = [40, 60]
    labels = ["Renewable", "Grid"]
    c = PieChart(10*270, 10*127)
    c.addTitle2(TopLeft, "<*underline=8*>Utilization This Period", "verdanab.ttf", 72, 0x000000).setMargin2(0, 0, 30, 0)

    c.setColors2(DataColor, [0x007437,0x5a8f47]) 
    c.setPieSize((10*270)/1.9, (10*127)/1.9, ((10*127)/2.5))
    c.setData(data, labels)
    c.setLabelStyle('verdana.ttf', 64)
    c.makeChart("images/SampleGraph1.png")
   
    Elements.append(Image('images/SampleGraph1.png', 270*.9, 127*.9))
    Elements.append(UseUpSpace())


    # populate graph two 
    
    # construct period environmental benefit


    environmentalBenefit = [
        [Paragraph("<b><u>Environmental Benefit This Period</u></b>", styles['BillLabelSm']), Paragraph('', styles['BillLabelSm'])], 
        [Paragraph("<b>Pounds Carbon Offset</b>", styles['BillLabelSm']), Paragraph("0.0", styles['BillFieldSm'])]
    ]

    t = Table(environmentalBenefit, [180,90])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'LEFT'), ('ALIGN',(1,0),(1,-1),'LEFT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5)]))

    Elements.append(t)
    Elements.append(UseUpSpace())


    # populate graph four 
    
    # construct annual production graph
    data = [30, 28, 40, 55, 75, 68, 54, 60, 50, 62, 75, 65]
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    c = XYChart(10*270, 10*127)
    c.setPlotArea((10*270)/12, (10*127)/6.5, (10*270)*.9, (10*127)*.70)
    c.setColors2(DataColor, [0x9bbb59]) 
    c.addBarLayer(data)
    c.addTitle2(TopLeft, "<*underline=8*>Annual Production", "verdanab.ttf", 72, 0x000000).setMargin2(0, 0, 30, 0)
    c.yAxis().setLabelStyle('verdana.ttf', 64)
    c.yAxis().setTickDensity(100)
    c.xAxis().setLabels(labels)
    c.xAxis().setLabelStyle('verdana.ttf', 64)
    c.makeChart("images/SampleGraph3.png")    

    Elements.append(Image('images/SampleGraph3.png', 270*.9, 127*.9))
    Elements.append(UseUpSpace())


    # populate graph four 
    
    # construct system life cumulative numbers table

    systemLife = [
        [Paragraph("<b><u>Total System Life</u></b>", styles['BillLabelSm']), Paragraph('', styles['BillLabelSm'])], 
        [Paragraph("<b>Pounds Carbon Offset</b>", styles['BillLabelSm']), Paragraph("0.0", styles['BillFieldSm'])]
    ]

    t = Table(systemLife, [180,90])
    t.setStyle(TableStyle([('ALIGN',(0,0),(0,-1),'LEFT'), ('ALIGN',(1,0),(1,-1),'LEFT'), ('BOTTOMPADDING', (0,0),(-1,-1), 3), ('TOPPADDING', (0,0),(-1,-1), 5)]))

    Elements.append(t)
    Elements.append(UseUpSpace())


    #
    # Second Page
    #
    
    Elements.append(NextPageTemplate("SecondPage"));
    Elements.append(PageBreak());

    Elements.append(image)

    Elements.append(Paragraph("Content Frame  asdasd asdas asd as asd asd asd asd asd asd asd asd", styles['Normal']))
    #Elements.append(UseUpSpace())
     
    doc.setProgressCallBack(progress)
    doc.build(Elements)

     
if __name__ == "__main__":  
    go()