import urllib
import threading
import os


class loadImageThread(threading.Thread):

    def __init__(self, website, image_list, dowloaded_list, FilePath):
        threading.Thread.__init__(self)
        self.website = str(website)
        self.filepath = FilePath
        self.image_list = image_list
        self.mDowloaded_list = dowloaded_list

    def run(self):
        for image_url in self.image_list:
            print(self.website + image_url)
            urllib.urlretrieve(
                self.website + image_url,
                self.filepath + image_url)
            self.mDowloaded_list.append(
                os.path.abspath(
                    self.filepath + image_url))


def loadOnlineImgMul(
        website,
        image_list,
        thread_num,
        dowloaded_image_list,
        FilePath):
    if len(image_list) / thread_num == 0:
        thread_num = 1
    if thread_num == 1:
        num_per_thread = len(image_list)
    else:
        num_per_thread = len(image_list) / thread_num
    for i in range(thread_num + 1):
        if (i + 1) * num_per_thread > len(image_list):
            t = loadImageThread(
                website,
                image_list[
                    i * num_per_thread:-1],
                dowloaded_image_list,
                FilePath)
            t.start()
        else:
            t = loadImageThread(
                website,
                image_list[
                    i *
                    num_per_thread:(
                        i +
                        1) *
                    num_per_thread],
                dowloaded_image_list,
                FilePath)
            t.start()
