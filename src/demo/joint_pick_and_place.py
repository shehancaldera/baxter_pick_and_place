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


import logging

import rospy

import settings
from instruction import client


# Set up logging
_logger = logging.getLogger('demo')
_logger.setLevel(logging.INFO)
_default_loghandler = logging.StreamHandler()
_default_loghandler.setLevel(logging.INFO)
_default_loghandler.setFormatter(logging.Formatter('[%(name)s][%(levelname)s] %(message)s'))
_logger.addHandler(_default_loghandler)


def remove_default_loghandler():
    """Call this to mute this library or to prevent duplicate messages
    when adding another log handler to the logger named 'demo'."""
    _logger.removeHandler(_default_loghandler)


class PickAndPlace(object):
    def __init__(self, robot, servo, camera, detection, segmentation):
        self._robot = robot
        self._servo = servo
        self._camera = camera
        self._detection = detection
        self._segmentation = segmentation

        # safety offset when approaching a pose [x, y, z, r, p, y]
        self._approach_offset = [0, 0, 0.1, 0, 0, 0]

    def calibrate(self):
        # TODO: implement calibration routines
        # Either perform calibration or load existing calibration file(s)
        _logger.info("Performing calibration/loading calibration file.")

        # height of table
        calibration_pose = [0, 0, 0, 0, 0, 0]
        #  move to calibration_pose
        #  repeat
        #    ask if indicated area under end effector is empty from objects
        #    if not, ask to clear the area from objects
        #    else, proceed
        #  use distance sensor to measure distance to table
        self._robot.distance_to_table = 0.27
        self._robot.z_table = -(self._robot.distance_to_table - calibration_pose[2])
        #  compute height of table in robot coordinates and store it
        # mean color of table when empty
        #  record hand camera image and store it

        # Measured meters per pixel @ 1 m distance
        for arm in ['left', 'right']:
            self._robot.cameras[arm].meters_per_pixel = 0.0025

        # discretize table (looking for empty spots)
        # with valid poses and configs

        # external camera relative to Baxter coordinates
        pass

    def _get_approach_pose(self, pose):
        """Compute a pose safe for approaching the given pose by adding some
        safety offset.

        :param pose: The pose we wish to approach.
        :return: The approach pose (the original pose + the safety offset).
        """
        return [a + b for a, b in zip(pose, self._approach_offset)]

    def perform(self):
        """Perform the pick-and-place demonstration.

        :return:
        """
        _logger.info('Starting pick and place demonstration.')
        instr = client.wait_for_instruction()
        while not rospy.is_shutdown() and instr != 'exit':
            obj_id, tgt_id = instr.split(' ')
            _logger.info('Instructed to take {} and {}.'.format(
                'the {}'.format(obj_id) if obj_id != 'hand' else "'it'",
                'give it to you' if tgt_id == 'hand' else 'put it on the table')
            )

            _logger.info('Looking for {} and estimate its pose.'.format(obj_id))
            if obj_id == 'hand':
                obj_pose = self._camera.estimate_hand_position()
                while obj_pose is None:
                    _logger.warning("No hand position estimate was found! "
                                    "Please relocate your hand holding the object.")
                    # TODO: adapt this sleep time
                    rospy.sleep(1.0)
                    obj_pose = self._camera.estimate_hand_position()
                obj_pose += [0, 0, 0]
            else:
                img_color = self._camera.color.collect_image()
                img_depth = self._camera.depth.collect_image()
                det = self._detection.detect_object(image=img_color,
                                                    object_id=obj_id,
                                                    threshold=0.8)
                obj_pose = self._camera.estimate_object_position(img_rgb=img_color,
                                                                 bbox=det['box'],
                                                                 img_depth=img_depth)
                while obj_pose is None:
                    _logger.info("I did not find the {}!".format(obj_id))
                    # TODO: implement looking for the object
                    # move hand camera along pre-defined trajectory over the table
                    # apply object detection until object found or failure
                    # compute 3d coordinates from detection and known height of table
                obj_pose += [0, 0, 0]
            appr_pose = self._get_approach_pose(pose=obj_pose)
            try:
                arm, appr_cfg = self._robot.ik_either_limb(pose=appr_pose)
            except ValueError:
                _logger.warning("I abort this task! Please start over.")
                instr = client.wait_for_instruction()
                continue

            if tgt_id == 'table':
                _logger.info('Looking for a spot to put the object down.')
                # TODO: implement looking for an empty spot on the table
                # move to calibration_pose
                # record an image with the hand camera
                # randomly select patches of appropriate size and compare them to the
                #  corresponding patch in the image stored during calibration
                #  http://jeffkreeftmeijer.com/2011/comparing-images-and-creating-image-diffs/
                # if difference < threshold, patch is assumed to be empty
                tgt_pose = [0.5, 0.2, 0.3, 0, 0, 0]

            _logger.info('Picking up the object.')

            _logger.info('Attempting to grasp object with {} limb.'.format(arm))
            success = False
            while not success:
                self._robot.move_to(config=appr_cfg)
                _logger.info('Using visual servoing to grasp object.')
                if obj_id == 'hand':
                    self._servo['hand'].servo(arm=arm, object_id=obj_id)
                else:
                    self._servo['table'].servo(arm=arm, object_id=obj_id)
                if self._robot.grasp(arm):
                    success = True
                else:
                    _logger.info('Something went wrong. I will try again.')
                    self._robot.release(arm)
            self._robot.move_to(config=settings.top_cfgs[arm])

            _logger.info('Placing the object.')
            if tgt_id == 'table':
                appr_pose = self._get_approach_pose(pose=tgt_pose)
                try:
                    appr_cfg = self._robot.inverse_kinematics(arm=arm, pose=appr_pose)
                except ValueError as e:
                    # TODO: how to handle this case?
                    raise e
                self._robot.move_to(config=appr_cfg)
                try:
                    tgt_cfg = self._robot.inverse_kinematics(arm=arm, pose=tgt_pose)
                except ValueError as e:
                    # TODO: handle this case similar to above
                    raise e
                self._robot.move_to(config=tgt_cfg)
                self._robot.release()
                self._robot.move_to(config=appr_cfg)
            else:
                tgt_pose = self._camera.estimate_hand_position()
                while tgt_pose is None:
                    _logger.warning("No hand position estimate was found! "
                                    "Please relocate your hand.")
                    # TODO: adapt this sleep time
                    rospy.sleep(1.0)
                    tgt_pose = self._camera.estimate_hand_position()
                tgt_pose += [0, 0, 0]
                try:
                    tgt_cfg = self._robot.inverse_kinematics(arm=arm, pose=tgt_pose)
                except ValueError as e:
                    # TODO: handle this case similar to above
                    raise e
                self._robot.move_to(config=tgt_cfg)
                _logger.info('Please take the object from me.')
                while self._robot.is_gripping(arm):
                    rospy.sleep(0.5)
                self._robot.release()
            self._robot.move_to(config=settings.top_cfgs[arm])
            self._robot.move_to_neutral(arm=arm)
            _logger.info('I finished my task.')

            instr = client.wait_for_instruction()
        _logger.info('Exiting pick and place demonstration.')
