# -*- coding:utf-8 -*-
"""
@author: xuesu

"""
import exceptions.base_exception


class WordTextSimilarInvalidEditorDistanceThreshold(exceptions.base_exception.IRBaseException):
    def __init__(self, pattern, node):
        message = "InvalidEditorDistance for pattern: {} at node: {}".format(pattern, node.add_tostr())
        super(WordTextSimilarInvalidEditorDistanceThreshold, self).__init__(message)
        self.pattern = pattern
        self.node = node
