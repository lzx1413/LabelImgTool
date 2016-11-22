'''
this file define a class to save the result of the mask of parse
the mask will be save as a gray image using different color to represent different
object
'''
import cv2
import numpy as np
import logging


class label_mask_writer:

    def __init__(
            self,
            label_num_dict,
            save_file_path,
            image_height,
            image_width):
        self.label_num_dict = label_num_dict
        self.save_file_path = save_file_path
        self.image_height = image_height
        self.image_width = image_width
        self.labels = []
        self.shapes = []

    def save_mask_image(self, shapes):
        for shape in shapes:
            self.add_mask_label(shape['label'])
            self.add_shape_points(shape['points'])
            image = self.get_mask_image()
            cv2.imwrite(self.save_file_path, image)

    def add_mask_label(self, label):
        self.labels.append(label)

    def add_shape_points(self, shape_points):
        self.shapes.append(shape_points)

    def get_mask_image(self):
        '''
        convert label and shapes to gray image mask
        :return: gray image mask
        '''
        assert len(self.labels) == len(self.shapes)
        mask_back = np.zeros(
            (self.image_height, self.image_width, 1), np.uint8)
        if self.labels:
            index = 0
            for label in self.labels:
                color = self.label_num_dict[label]
                vertex = self.shapes[index]
                index += 1
                vertex = np.asarray(vertex, 'int32')
                cv2.fillConvexPoly(mask_back, vertex, color)
        else:
            logging.error('there are no shapes to save !')
        return mask_back
