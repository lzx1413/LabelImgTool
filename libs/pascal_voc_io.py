import sys
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement
from xml.dom import minidom
from lxml import etree


class PascalVocWriter:
    def __init__(self, foldername, filename, imgSize, databaseSrc='Unknown', localImgPath=None, shape_type=None):
        self.foldername = foldername
        self.filename = filename
        self.databaseSrc = databaseSrc
        self.imgSize = imgSize
        self.boxlist = []
        self.localImgPath = localImgPath
        self.shape_type = shape_type

    def prettify(self, elem):
        """
            Return a pretty-printed XML string for the Element.
        """
        rough_string = ElementTree.tostring(elem, 'utf8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="\t")

    def genXML(self):
        """
            Return XML root
        """
        # Check conditions
        '''
        if self.filename is None or \
                        self.foldername is None or \
                        self.imgSize is None or \
                        len(self.boxlist) <= 0:
        '''
        if self.filename is None or \
                        len(self.boxlist) <= 0:
            return None

        top = Element('annotation')
        folder = SubElement(top, 'folder')
        folder.text = self.foldername

        filename = SubElement(top, 'filename')
        filename.text = self.filename

        localImgPath = SubElement(top, 'path')
        self.localImgPath = self.localImgPath.split('/')[-1]
        localImgPath.text = self.localImgPath

        source = SubElement(top, 'source')
        database = SubElement(source, 'database')
        database.text = self.databaseSrc

        if self.imgSize:
            size_part = SubElement(top, 'size')
            width = SubElement(size_part, 'width')
            height = SubElement(size_part, 'height')
            depth = SubElement(size_part, 'depth')
            width.text = str(self.imgSize[1])
            height.text = str(self.imgSize[0])
            if len(self.imgSize) == 3:
                depth.text = str(self.imgSize[2])
            else:
                depth.text = '1'

        segmented = SubElement(top, 'segmented')
        segmented.text = '0'
        shape_type = SubElement(top, 'shape_type')
        shape_type.text = self.shape_type
        return top

    def addBndBox(self, xmin, ymin, xmax, ymax, name):
        bndbox = {'xmin': xmin, 'ymin': ymin, 'xmax': xmax, 'ymax': ymax}
        bndbox['name'] = name
        self.boxlist.append(bndbox)

    def addPolygon(self, shape, name):
        polygon = {}
        i = 0
        for point in shape:
            polygon[i] = point
            i = i + 1
        polygon['name'] = name
        polygon['point_num'] = str(len(shape))
        print 'point num is ', str(len(shape))
        self.boxlist.append(polygon)

    def appendObjects(self, top):
        for each_object in self.boxlist:
            object_item = SubElement(top, 'object')
            if each_object['name']:
                name = SubElement(object_item, 'name')
                name.text = str(each_object['name'])
            pose = SubElement(object_item, 'pose')
            pose.text = "Unspecified"
            truncated = SubElement(object_item, 'truncated')
            truncated.text = "0"
            difficult = SubElement(object_item, 'difficult')
            difficult.text = "0"
            if self.shape_type == 'RECT':
                bndbox = SubElement(object_item, 'bndbox')
                xmin = SubElement(bndbox, 'xmin')
                xmin.text = str(each_object['xmin'])
                ymin = SubElement(bndbox, 'ymin')
                ymin.text = str(each_object['ymin'])
                xmax = SubElement(bndbox, 'xmax')
                xmax.text = str(each_object['xmax'])
                ymax = SubElement(bndbox, 'ymax')
                ymax.text = str(each_object['ymax'])
            elif self.shape_type == 'POLYGON':
                polygon = SubElement(object_item, 'polygon')
                for i in xrange(int(each_object['point_num'])):
                    point = SubElement(polygon, 'point' + str(i))
                    point.text = str(int(each_object[i][0])) + ',' + str(int(each_object[i][1]))
                    print i, point.text

    def save(self, targetFile=None):
        root = self.genXML()
        self.appendObjects(root)
        out_file = None
        if targetFile is None:
            out_file = open(self.filename + '.xml', 'w')
        else:
            out_file = open(targetFile, 'w')
        print root
        out_file.write(self.prettify(root))
        ##out_file.write(root)
        out_file.close()


class PascalVocReader:
    def __init__(self, filepath):
        ## shapes type:
        ## [labbel, [(x1,y1), (x2,y2), (x3,y3), (x4,y4)], color, color]
        self.shapes = []
        self.filepath = filepath
        self.shape_type = None
        self.image_size = []
        self.parseXML()

    def getShapes(self):
        return self.shapes
    def getShapeType(self):
        return self.shape_type

    def addPolygonShape(self,label,points):
        points = [(point[0],point[1]) for point in points]
        self.shapes.append((label,points,None,None,1))
    def get_img_size(self):
        if self.image_size:
            return self.image_size

    def addShape(self, label, rect):
        xmin = rect[0]
        ymin = rect[1]
        xmax = rect[2]
        ymax = rect[3]
        points = [(xmin, ymin), (xmin, ymax), (xmax, ymax), (xmax, ymin)]
        self.shapes.append((label, points, None, None,0))

    def parseXML(self):
        assert self.filepath.endswith('.xml'), "Unsupport file format"
        xmltree = ElementTree.parse(self.filepath).getroot()
        filename = xmltree.find('filename').text
        self.shape_type = xmltree.find('shape_type').text
        self.image_size.append(int(xmltree.find('size').find('width').text))
        self.image_size.append(int(xmltree.find('size').find('height').text))
        if self.shape_type == 'RECT':
            for object_iter in xmltree.findall('object'):
                rects = []
                bndbox = object_iter.find("bndbox")
                rects.append([int(it.text) for it in bndbox])
                label = object_iter.find('name').text
                for rect in rects:
                    self.addShape(label, rect)
            return True
        elif self.shape_type == 'POLYGON':
            for object_iter in xmltree.findall('object'):
                points = []
                polygons = object_iter.find("polygon")
                label = object_iter.find('name').text
                for point in polygons:
                    point = point.text.split(',')
                    point = [int(dot) for dot in point]
                    points.append(point)
                self.addPolygonShape(label,points)
        else:
            print 'unsupportable shape type'


# tempParseReader = PascalVocReader('test.xml')
# print tempParseReader.getShapes()
"""
# Test
tmp = PascalVocWriter('temp','test', (10,20,3))
tmp.addBndBox(10,10,20,30,'chair')
tmp.addBndBox(1,1,600,600,'car')
tmp.save()
"""
