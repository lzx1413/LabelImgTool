import sys

sys.path.append("..")
import libs.labelFile as LF
from collections import defaultdict


def generate_shape_format(img_obj_dic):
    result_list = {}
    for key in img_obj_dic:
        objs = img_obj_dic[key]
        shapes = []
        for obj in objs:
            obj = obj.split(',')
            points = []
            x = int(obj[2])
            y = int(obj[3])
            width = int(obj[4])
            height = int(obj[5])
            points.append((x, y))
            points.append((x + width, y))
            points.append((x, y + height))
            points.append((x + width, y + height))
            if len(obj) < 6:
                continue
            result = dict(label=obj[0], line_color=None, fill_color=None, points=points, shape_type=0
                          )
            shapes.append(result)
        result_list[key] = shapes
    return result_list


def generate_xml_file(input_file1, input_file2, result_path):
    image_list = []
    img_obj_dic = defaultdict(list)
    with open(input_file1) as f1:
        image_list = f1.readlines()
        image_list = [image.strip() for image in image_list]
    with open(input_file2) as f2:
        img_obj_list = f2.readlines()
        img_obj_list = [img_obj.strip() for img_obj in img_obj_list]
    head_index = 0
    tail_index = 0
    for image_item in image_list:
        image_item = image_item.split(',')
        tail_index = head_index + int(image_item[1])
        img_obj_dic[image_item[0] + 'b'] = img_obj_list[head_index:tail_index]
        head_index = tail_index
    format_dic = generate_shape_format(img_obj_dic)
    lf = LF.LabelFile()
    for key in format_dic:
        lf.savePascalVocFormat(result_path + key + '.xml', None, format_dic[key], key)

    print format_dic


if __name__ == "__main__":
    generate_xml_file("keyframeIndx.txt", "autoDetectBox.txt", "./")
