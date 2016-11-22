#coding:utf-8
from libs.pascal_voc_io import PascalVocReader
import save_mask_image
import json
import os
from libs.canvas import Canvas
def get_name_dic(file_path):
    with open(file_path) as infile:
        label_num_dic = json.load(infile)
        return label_num_dic
        '''
        items = infile.readlines()
        index = 0
        for item in items:
            item = item.strip().split(' ')
            for it in item:
                label_num_dic[it] = index
                index +=1
                '''

def get_image(filename,label_num_dic = None):
    tVocParseReader = PascalVocReader(filename)
    raw_shapes = tVocParseReader.getShapes()
    print raw_shapes
    def format_shape(s):
        label,points,aa,bb,c = s
        return dict(label=unicode(label),
                    points=[(int(p[0]), int(p[1])) for p in points])

    shapes = [format_shape(shape) for shape in raw_shapes]
    image_size = tVocParseReader.get_img_size()
    print image_size
    result_path = '/mask'+filename.split('/')[1].split('.')[0]+'.png'
    mask_writer = save_mask_image.label_mask_writer(label_num_dic, result_path, image_size[0],
                                                    image_size[1])
    mask_writer.save_mask_image(shapes)

if __name__ == '__main__':
    file_list = os.listdir('img_addition')
    print file_list
    label_num_dic = get_name_dic('label_num_dic.json')
    for file_name in file_list:
        get_image('img_addition/'+file_name,label_num_dic)
