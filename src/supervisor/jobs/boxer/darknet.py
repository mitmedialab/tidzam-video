from ctypes import *
from time import time

import math
import random
import numpy as np
import os,sys
from utils.custom_logging import debug, _DEBUG_LEVEL

from contextlib import contextmanager
import io
import tempfile
import ctypes

def sample(probs):
    s = sum(probs)
    probs = [a/s for a in probs]
    r = random.uniform(0, 1)
    for i in range(len(probs)):
        r = r - probs[i]
        if r <= 0:
            return i
    return len(probs)-1

def c_array(ctype, values):
    return (ctype * len(values))(*values)

class BOX(Structure):
    _fields_ = [("x", c_float),
                ("y", c_float),
                ("w", c_float),
                ("h", c_float)]

class IMAGE(Structure):
    _fields_ = [("w", c_int),
                ("h", c_int),
                ("c", c_int),
                ("data", POINTER(c_float))]

class METADATA(Structure):
    _fields_ = [("classes", c_int),
                ("names", POINTER(c_char_p))]

lib_path = os.path.dirname(__file__)+"/libdarknet.so"
lib = CDLL(lib_path, RTLD_GLOBAL)
lib.network_width.argtypes = [c_void_p]
lib.network_width.restype = c_int
lib.network_height.argtypes = [c_void_p]
lib.network_height.restype = c_int

predict = lib.network_predict
predict.argtypes = [c_void_p, POINTER(c_float)]
predict.restype = POINTER(c_float)

set_gpu = lib.cuda_set_device
set_gpu.argtypes = [c_int]

make_image = lib.make_image
make_image.argtypes = [c_int, c_int, c_int]
make_image.restype = IMAGE

make_boxes = lib.make_boxes
make_boxes.argtypes = [c_void_p]
make_boxes.restype = POINTER(BOX)

free_ptrs = lib.free_ptrs
free_ptrs.argtypes = [POINTER(c_void_p), c_int]

num_boxes = lib.num_boxes
num_boxes.argtypes = [c_void_p]
num_boxes.restype = c_int

make_probs = lib.make_probs
make_probs.argtypes = [c_void_p]
make_probs.restype = POINTER(POINTER(c_float))

detect = lib.network_predict
detect.argtypes = [c_void_p, IMAGE, c_float, c_float, c_float, POINTER(BOX), POINTER(POINTER(c_float))]

reset_rnn = lib.reset_rnn
reset_rnn.argtypes = [c_void_p]

load_net = lib.load_network
load_net.argtypes = [c_char_p, c_char_p, c_int]
load_net.restype = c_void_p

free_image = lib.free_image
free_image.argtypes = [IMAGE]

letterbox_image = lib.letterbox_image
letterbox_image.argtypes = [IMAGE, c_int, c_int]
letterbox_image.restype = IMAGE

load_meta = lib.get_metadata
lib.get_metadata.argtypes = [c_char_p]
lib.get_metadata.restype = METADATA

load_image = lib.load_image_color
load_image.argtypes = [c_char_p, c_int, c_int]
load_image.restype = IMAGE

rgbgr_image = lib.rgbgr_image
rgbgr_image.argtypes = [IMAGE]

predict_image = lib.network_predict_image
predict_image.argtypes = [c_void_p, IMAGE]
predict_image.restype = POINTER(c_float)

network_detect = lib.network_detect
network_detect.argtypes = [c_void_p, IMAGE, c_float, c_float, c_float, POINTER(BOX), POINTER(POINTER(c_float))]

c_stderr = ctypes.c_void_p.in_dll(lib, 'stderr')

@contextmanager
def stderr_redirector(stream):
    if _DEBUG_LEVEL > 1:
        yield
        return
    # The original fd stderr points to. Usually 1 on POSIX systems.
    original_stderr_fd = sys.stderr.old_std.fileno()

    def _redirect_stderr(to_fd):
        """Redirect stderr to the given file descriptor."""
        # Flush the C-level buffer stderr
        lib.fflush(c_stderr)
        # Flush and close sys.stderr - also closes the file descriptor (fd)
        try:
            sys.stderr.old_std.close()
        except:
            sys.stderr.close()
        # Make original_stderr_fd point to the same file as to_fd
        os.dup2(to_fd, original_stderr_fd)
        # Create a new sys.stderr that points to the redirected fd
        sys.stderr = io.TextIOWrapper(os.fdopen(original_stderr_fd, 'wb'))

    # Save a copy of the original stderr fd in saved_stderr_fd
    saved_stderr_fd = os.dup(original_stderr_fd)
    try:
        # Create a temporary file and redirect stderr to it
        tfile = tempfile.TemporaryFile(mode='w+b')
        _redirect_stderr(tfile.fileno())
        # Yield to caller, then redirect stderr back to the saved fd
        yield
        _redirect_stderr(saved_stderr_fd)
        # Copy contents of temporary file to the given stream
        tfile.flush()
        tfile.seek(0, io.SEEK_SET)
        stream.write(tfile.read())
    finally:
        tfile.close()
        os.close(saved_stderr_fd)

def classify(net, meta, im):
    out = predict_image(net, im)
    res = []
    for i in range(meta.classes):
        res.append((meta.names[i], out[i]))
    res = sorted(res, key=lambda x: -x[1])
    return res

class Stopwatch:

    def __init__(self):
        self.start = time()

    def print_now(self):
        print("ELAPSED: "+str(self.get_time()))


    def get_time(self):
        t = str(time()-self.start)
        self.start = time()

        return t

def detect(net, meta, image, thresh=.2, hier_thresh=.2, nms=.45, nb_classes=9418):
    sw = Stopwatch()
    debug("Darknet running on image...", 3)

    debug("DARKNET TIMINGS", 3)

    boxes = make_boxes(net)
    debug("MAKE_BOXES "+str(sw.get_time()), 3)

    probs = make_probs(net)
    debug("MAKE_PROBAS "+str(sw.get_time()), 3)

    num =   num_boxes(net)
    debug("NUM_BOXES "+str(sw.get_time()), 3)

    network_detect(net, image, thresh, hier_thresh, nms, boxes, probs)
    debug("DETECTION "+str(sw.get_time()), 3)

    res = []

    for j in range(num):
        arr = (ctypes.c_float * nb_classes).from_address(addressof(probs[j].contents))
        arr = np.ndarray(buffer=arr, dtype=np.float32, shape=(nb_classes))
        for i in np.where(arr > 0)[0]:
            res.append((meta.names[i], float(arr[int(i)]), (boxes[j].x, boxes[j].y, boxes[j].w, boxes[j].h)))
    debug("LABELISATION 1 "+str(sw.get_time()), 3)

    res = sorted(res, key=lambda x: -x[1])
    free_ptrs(cast(probs, POINTER(c_void_p)), num)

    #print((res))
    return res
