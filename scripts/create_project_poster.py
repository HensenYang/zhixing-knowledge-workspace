"""Vector A3 project poster; run with the bundled PDF runtime Python."""
from pathlib import Path
import math
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'pdf'
OUT.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
W, H = 841.89, 1190.55
INK, GREEN, LIGHT, GOLD, BG, MUTED = '#163E37', '#2B765C', '#DCEBCB', '#D7B474', '#F5F5EF', '#5D736A'
path = OUT / 'knowledge-in-motion-poster.pdf'
c = canvas.Canvas(str(path), pagesize=(W, H))
c.setTitle('Knowledge in Motion | Scientific Communication and Education')
c.setAuthor('ZhiXing Knowledge Workspace')

def rect(x, y, w, h, fill, radius=0, stroke=None):
    c.setFillColor(HexColor(fill))
    c.setStrokeColor(HexColor(stroke or fill))
    if radius:
        c.roundRect(x, H-y-h, w, h, radius, fill=1, stroke=bool(stroke))
    else:
        c.rect(x, H-y-h, w, h, fill=1, stroke=bool(stroke))

def text(x, y, value, size=12, color=INK, bold=False):
    c.setFont('Arial-Bold' if bold else 'Arial', size)
    c.setFillColor(HexColor(color))
    c.drawString(x, H-y-size, value)

def paragraph(x, y, width, value, size=12, color=MUTED, leading=None, bold=False, maxheight=None):
    style = ParagraphStyle('body', fontName='Arial-Bold' if bold else 'Arial', fontSize=size,
        leading=leading or size*1.5, textColor=HexColor(color), alignment=TA_LEFT)
    p = Paragraph(value, style)
    _, height = p.wrap(width, H)
    if maxheight is not None:
        assert height <= maxheight, (value, height, maxheight)
    p.drawOn(c, x, H-y-height)
    return height

def line(x1, y1, x2, y2, color, width=1):
    c.setStrokeColor(HexColor(color)); c.setLineWidth(width)
    c.line(x1, H-y1, x2, H-y2)

def arrow(x1, y1, x2, y2, color=GOLD, width=2):
    line(x1,y1,x2,y2,color,width)
    angle=math.atan2(y2-y1,x2-x1)
    for delta in [-0.5,0.5]:
        line(x2,y2,x2-7*math.cos(angle+delta),y2-7*math.sin(angle+delta),color,width)

def edge_label(x,y,value):
    tw=pdfmetrics.stringWidth(value,'Arial',9)
    rect(x-4,y-1,tw+8,14,INK,3)
    text(x,y,value,9,'#C2D6CD')

def node(x,y,width,label,detail,fill='#28544A',current=False):
    rect(x,y,width,52,fill,10, GOLD if not current else LIGHT)
    text(x+11,y+9,label,11,INK if current else '#FFFFFF',True)
    text(x+11,y+28,detail,8,INK if current else '#C2D6CD')

rect(0,0,W,H,BG)
rect(36,34,24,24,GREEN,7)
line(42,46,48,40,LIGHT,1.7); line(48,40,54,48,LIGHT,1.7)
for x,y in [(42,46),(48,40),(54,48)]:
    c.setFillColor(HexColor(LIGHT)); c.circle(x,H-y,2,fill=1,stroke=0)
text(70,37,'ZHIXING  /  KNOWLEDGE IN MOTION',13,INK,True)
text(568,40,'SCIENTIFIC COMMUNICATION + EDUCATION',9,GREEN,True)

text(36,86,'Make scientific',58,INK,True)
text(36,151,'knowledge',58,INK,True)
text(36,216,'navigable.',58,GREEN,True)
paragraph(39,293,733,'A relationship-driven workspace that turns papers, code and experiments<br/>into explorable, evidence-linked learning journeys.',17,INK,23,maxheight=50)

rect(36,362,770,272,INK,18)
text(58,385,'FROM INFORMATION TO UNDERSTANDING',9,LIGHT,True)
paragraph(58,415,220,'Read the evidence.<br/>Follow the connections.<br/>Explain the science.',20,'#FFFFFF',28,maxheight=100)
paragraph(58,535,200,'Your reading position and visited path stay visible as you explore.',11,'#BDD3C8',16,maxheight=55)

arrow(448,421,527,465,GOLD)
arrow(584,495,680,552,GOLD)
arrow(690,418,595,463,'#628E7C',1.4)
arrow(447,559,532,499,'#628E7C',1.4)
arrow(713,547,715,433,'#628E7C',1.4)
edge_label(463,427,'supports')
edge_label(604,516,'uses')
edge_label(600,431,'questions')
edge_label(469,525,'implements')
edge_label(721,476,'evaluates')
node(336,395,112,'Paper','Source evidence')
node(520,456,116,'Core concept','You are reading here',LIGHT,True)
node(667,391,115,'Question','Open research gap')
node(336,546,112,'Code','Implementation')
node(667,546,115,'Method','Next reading step')
text(339,610,'CURRENT NOTE',8,LIGHT,True)
text(459,610,'VISITED CONNECTION',8,GOLD,True)
text(620,610,'CLICK TO CONTINUE READING',8,'#C2D6CD',True)

text(36,653,'ONE FRAMEWORK. MANY DISCIPLINES.',11,GREEN,True)
text(393,653,'Existing embodied-AI pilot: 60 notes / 91 relations / 1 canvas',10,MUTED)

rect(36,689,374,195,'#FFFFFF',12)
rect(426,689,380,195,'#FFFFFF',12)
text(55,706,'01 / WHY IT MATTERS',9,GREEN,True)
text(55,728,'Motivation',24,INK,True)
paragraph(55,771,333,'Scientific knowledge spans papers, code, datasets and experiments. Understanding depends on seeing how they connect.<br/><br/>Make those connections explorable so researchers can explain evidence and educators can guide discovery.',12,INK,17,maxheight=105)
text(445,706,'02 / THE DESIGN QUESTION',9,GREEN,True)
text(445,728,'Problem definition',24,INK,True)
paragraph(445,771,339,'Folders and linear notes hide prerequisites, evidence and methodological links. Readers lose context between resources.<br/><br/>How can a knowledge workspace make scientific reasoning visible while preserving a learner\'s place?',12,INK,17,maxheight=105)

text(36,909,'03 / BUILD, DEMONSTRATE, EVALUATE',9,GREEN,True)
text(36,929,'Hackathon target',28,INK,True)
paragraph(36,973,760,'Build on the working prototype to demonstrate a guided, evidence-linked learning journey and test its value for scientific explanation and cross-domain teaching.',13,INK,18,maxheight=42)

cards=[('TRACE','Follow a claim back to its source.'),('EXPLORE','Navigate concepts, methods and evidence.'),('EXPLAIN','Create a learning path for another audience.')]
for i,(title,body) in enumerate(cards):
    x=36+i*262
    rect(x,1030,246,77,LIGHT if i==0 else '#E7ECE3',9)
    text(x+15,1043,title,12,GREEN,True)
    paragraph(x+15,1065,214,body,11,INK,14,maxheight=30)
text(36,1124,'Pilot evaluation: source traceability, explanation clarity and navigation.',11,MUTED)
line(36,1153,806,1153,'#C9D5C8',1)
text(36,1165,'LOCAL BROWSER WORKSPACE  |  React + FastAPI + PostgreSQL',9,MUTED)
text(575,1165,'Prototype capabilities; educational impact to be evaluated.',8,MUTED)
c.showPage(); c.save()

intro='''# Knowledge in Motion
## A relationship-driven workspace for scientific communication and education

**Motivation:** Scientific knowledge is distributed across papers, code, datasets and experiments. Researchers and learners need to understand how these resources connect, not simply store them. Our project makes these connections visible and explorable, supporting evidence-based explanation, discussion and guided learning across disciplines.

**Problem definition:** Folders and linear notes often hide conceptual prerequisites, evidence and methodological relationships. Readers lose context when moving between resources, and educators must repeatedly reconstruct the same learning paths. The challenge is to make scientific reasoning traceable while helping learners understand where they are and where to explore next.

**Hackathon target:** Demonstrate and evaluate a browser-based knowledge workspace with editable, typed relationships, source-linked notes, a local graph that follows the current reading position, and revisitable learning paths. Use the existing embodied-AI collection as an initial case study, then test a cross-domain teaching scenario and assess source traceability, explanation clarity and navigation.

## 中文简介

**动机（Motivation）：** 科学知识分散在论文、代码、数据集和实验中。研究者与学习者需要理解这些材料之间的联系。项目将联系转化为可视化、可探索的知识网络，用于有证据支持的科学解释、讨论和跨学科学习。

**问题定义（Problem definition）：** 文件夹与线性笔记难以呈现概念前置条件、证据链和方法关联，读者在切换资料时容易失去上下文，教师也需要反复重建讲解路径。核心问题是：如何让科学推理过程可追溯，并帮助学习者清楚当前位置和下一步探索方向？

**黑客松目标（Hackathon target）：** 演示并评估一个浏览器知识工作台：连接带出处的笔记，编辑关系类型，让局部图跟随当前阅读位置，并支持沿路径回看。以已有具身智能资料为首个案例，进一步试验其他学科的教学场景，通过来源追溯、解释清晰度与导航体验评估价值。

现有能力：本机浏览器工作台、笔记与关系编辑、图谱和自由画布、阅读位置与路径跟踪、实验记录及备份。待验证目标：跨领域教学适用性和教育效果。不会将已有60个条目和91条关系当作学习效果证据。
'''
(OUT/'project-introduction.md').write_text(intro,encoding='utf-8')
print(path)
