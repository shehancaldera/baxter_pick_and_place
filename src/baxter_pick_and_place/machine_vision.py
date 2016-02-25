# Copyright (c) 2016, BRML
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import cv2
import matplotlib.pyplot as plt
import numpy as np

from baxter_pick_and_place.image import imgmsg2img


def segment_area(imgmsg, outpath=None, th=200, c_low=50, c_high=270,
                 ff_connectivity=4, a_low=100, a_high=200):
    """ Segment connected components on an image based on area using
    machine vision algorithms of increasing complexity.
    :param imgmsg: a ROS image message
    :param outpath: the path to where to write intermediate images to
    :param th: threshold for binary thresholding operation
    :param c_low: lower Canny threshold
    :param c_high: upper Canny threshold
    :param ff_connectivity: neighborhood relation (4, 8) to use for flood fill
    operation
    :param a_low: lower bound for contour area
    :param a_high: upper bound for contour area
    :returns: a tuple (rroi, roi) containing the rotated roi and corners and
    the upright roi enclosing the connected component
    """
    img = imgmsg2img(imgmsg)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    equ = cv2.equalizeHist(gray)

    # try binary threshold
    _, thresh = cv2.threshold(equ, th, 255, cv2.THRESH_BINARY)
    contour = _extract_contour(thresh, c_low, c_high, a_low, a_high)
    if contour is not None:
        array = thresh
        title = 'threshold'
    else:  # try opening to remove small regions
        kernel = np.ones((2, 2), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel,
                                   iterations=1)
        contour = _extract_contour(opening, c_low, c_high, a_low, a_high)
        if contour is not None:
            array = opening
            title = 'opening'
        else:  # try outline of segmented regions
            kernel = np.ones((2, 2), np.uint8)
            closing = cv2.morphologyEx(opening, cv2.MORPH_OPEN, kernel,
                                       iterations=1)
            outline = cv2.morphologyEx(closing, cv2.MORPH_GRADIENT, kernel,
                                       iterations=2)
            contour = _extract_contour(outline, c_low, c_high, a_low, a_high)
            if contour is not None:
                array = outline
                title = 'outline'
            else:  # see if flood-filling the image helps
                h, w = outline.shape[:2]
                mask = np.zeros((h+2, w+2), np.uint8)
                mask[1:-1, 1:-1] = outline
                seed_pt = (mask.shape[0], 0)
                flooded = gray.copy()
                flags = ff_connectivity | cv2.FLOODFILL_FIXED_RANGE
                cv2.floodFill(flooded, mask, seed_pt, (255, 255, 255),
                              (50,)*3, (255,)*3, flags)
                contour = _extract_contour(flooded, c_low, c_high,
                                           a_low, a_high)
                if contour is not None:
                    array = flooded
                    title = 'flooded'
    if contour is None:
        raise ValueError('No contour found!')

    # rotated roi
    rrect = cv2.minAreaRect(contour)
    box = cv2.cv.BoxPoints(rrect)
    # upright roi
    x, y, w, h = cv2.boundingRect(contour)

    if outpath:
        plt.figure(figsize=(11, 20))
        plt.subplot(121)
        plt.imshow(array, cmap='gray')
        plt.title(title)

        sample = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # rotated roi
        b = np.int0(box)
        cv2.drawContours(sample, [b], 0, (0, 255, 0), 2)
        cv2.circle(sample, (int(rrect[0][0]), int(rrect[0][1])), 4,
                   (0, 255, 0), 2)
        # upright roi
        cv2.rectangle(sample, (x, y), (x+w, y+h), (255, 0, 0), 2)
        cv2.circle(sample, (x+w/2, y+h/2), 3, (255, 0, 0), 2)
        plt.subplot(122)
        plt.imshow(sample)

        plt.savefig(outpath + '_contours.jpg', bbox_inches='tight')
        plt.close()

    return (rrect, box), (x, y, w, h)


def segment_red_area(imgmsg, outpath=None, th=200, c_low=50, c_high=270,
                     a_low=100, a_high=200):
    """ Segment connected components on an image based on red color and area.
    :param imgmsg: a ROS image message
    :param outpath: the path to where to write intermediate images to
    :param th: threshold for binary thresholding operation
    :param c_low: lower Canny threshold
    :param c_high: upper Canny threshold
    :param a_low: lower bound for contour area
    :param a_high: upper bound for contour area
    :returns: a tuple (rroi, roi) containing the rotated roi and corners and
    the upright roi enclosing the connected component
    """
    img = imgmsg2img(imgmsg)

    # look only at red channel
    red = cv2.split(img)[2]
    _, thresh = cv2.threshold(red, th, 255, cv2.THRESH_BINARY)
    contour = _extract_contour(thresh, c_low, c_high, a_low, a_high)
    if contour is None:
        raise ValueError('No contour found!')

    # rotated roi
    rrect = cv2.minAreaRect(contour)
    box = cv2.cv.BoxPoints(rrect)
    # upright roi
    x, y, w, h = cv2.boundingRect(contour)

    if outpath:
        plt.figure(figsize=(11, 20))
        plt.subplot(131)
        plt.imshow(red, cmap='gray')
        plt.subplot(132)
        plt.imshow(thresh, cmap='gray')
        sample = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # rotated roi
        b = np.int0(box)
        cv2.drawContours(sample, [b], 0, (0, 255, 0), 2)
        cv2.circle(sample, (int(rrect[0][0]), int(rrect[0][1])), 4,
                   (0, 255, 0), 2)
        # upright roi
        cv2.rectangle(sample, (x, y), (x+w, y+h), (255, 0, 0), 2)
        cv2.circle(sample, (x+w/2, y+h/2), 3, (255, 0, 0), 2)
        plt.subplot(133)
        plt.imshow(sample)
        plt.savefig(outpath + '_roi.jpg', bbox_inches='tight')
        plt.close()

    return (rrect, box), (x, y, w, h)


def segment_blue_area(imgmsg, outpath=None, th=200, c_low=50, c_high=270,
                      a_low=100, a_high=200):
    """ Segment connected components on an image based on red color and area.
    :param imgmsg: a ROS image message
    :param outpath: the path to where to write intermediate images to
    :param th: threshold for binary thresholding operation
    :param c_low: lower Canny threshold
    :param c_high: upper Canny threshold
    :param a_low: lower bound for contour area
    :param a_high: upper bound for contour area
    :returns: a tuple (rroi, roi) containing the rotated roi and corners and
    the upright roi enclosing the connected component
    """
    img = imgmsg2img(imgmsg)

    # look only at blue channel
    blue = cv2.split(img)[0]
    _, thresh = cv2.threshold(blue, th, 255, cv2.THRESH_BINARY)
    contour = _extract_contour(thresh, c_low, c_high, a_low, a_high)
    if contour is None:
        raise ValueError('No contour found!')

    # rotated roi
    rrect = cv2.minAreaRect(contour)
    box = cv2.cv.BoxPoints(rrect)
    # upright roi
    x, y, w, h = cv2.boundingRect(contour)

    if outpath:
        plt.figure(figsize=(11, 20))
        plt.subplot(131)
        plt.imshow(blue, cmap='gray')
        plt.subplot(132)
        plt.imshow(thresh, cmap='gray')
        sample = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # rotated roi
        b = np.int0(box)
        cv2.drawContours(sample, [b], 0, (0, 255, 0), 2)
        cv2.circle(sample, (int(rrect[0][0]), int(rrect[0][1])), 4,
                   (0, 255, 0), 2)
        # upright roi
        cv2.rectangle(sample, (x, y), (x+w, y+h), (255, 0, 0), 2)
        cv2.circle(sample, (x+w/2, y+h/2), 3, (255, 0, 0), 2)
        plt.subplot(133)
        plt.imshow(sample)
        plt.savefig(outpath + '_roi.jpg', bbox_inches='tight')
        plt.close()

    return (rrect, box), (x, y, w, h)


def _extract_contour(img, c_low=50, c_high=270, a_low=100, a_high=200):
    """ Apply Canny edge detection to an image and return maximal
    contour found.
    :param img: the image to work on
    :param c_low: lower Canny threshold
    :param c_high: upper Canny threshold
    :param a_low: lower bound for contour area
    :param a_high: upper bound for contour area
    :returns: the found contour, or None
    """
    canny = cv2.Canny(img, c_low, c_high, apertureSize=3)
    kernel = np.ones((3, 3), np.uint8)
    canny = cv2.morphologyEx(canny, cv2.MORPH_CLOSE, kernel,
                             iterations=1)

    contours, _ = cv2.findContours(canny, cv2.RETR_LIST,
                                   cv2.CHAIN_APPROX_SIMPLE)
    max_area = 0.0
    contour = None
    for c in contours:
        area = cv2.contourArea(c)
        if a_low < area < a_high:
            if area > max_area:
                max_area = area
                contour = c
    return contour
