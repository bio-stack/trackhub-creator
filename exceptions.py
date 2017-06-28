# 
# Author    : Manuel Bernal Llinares
# Project   : trackhub-creator
# Timestamp : 28-06-2017 10:16
# ---
# © 2017 Manuel Bernal Llinares <mbdebian@gmail.com>
# All rights reserved.
# 

"""
Application wide exceptions
"""


class AppException(Exception):
	def __init__(self, value):
		self.value = value

	def __str__(self):
		return repr(self.value)