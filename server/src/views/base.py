"""

UUDEX

Copyright © 2021, Battelle Memorial Institute

1. Battelle Memorial Institute (hereinafter Battelle) hereby grants
permission to any person or entity lawfully obtaining a copy of this
software and associated documentation files (hereinafter “the Software”)
to redistribute and use the Software in source and binary forms, with or
without modification.  Such person or entity may use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software, and
may permit others to do so, subject to the following conditions:

   - Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimers.
   - Redistributions in binary form must reproduce the above copyright notice,
     this list of conditions and the following disclaimer in the documentation
     and/or other materials provided with the distribution.
   - Other than as used herein, neither the name Battelle Memorial Institute
     or Battelle may be used in any form whatsoever without the express
     written consent of Battelle.

2. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

import base64

import flask_restful
from flask_restful import reqparse, fields

# custom type to binary to base64
class Base64Item(fields.Raw):
    def format(self, value):
        return base64.b64encode(value).decode("utf-8")

class ModelViewBase:
    _post_parser = None
    _patch_parser = None
    _resp_fields = None

    @classmethod
    def _build_resp_fields(cls):
        pass  # virtual

    @classmethod
    def _build_post_parser(cls):
        pass  # virtual

    @classmethod
    def _build_put_parser(cls):
        cls._patch_parser = cls._post_parser.copy()

        for item in cls._patch_parser.args:
            if item.required:
                item.nullable = False
            item.required = False
            item.store_missing = False

    @classmethod
    def generate_resp(cls, data, envelope=None):
        if cls._resp_fields is None:
            cls._build_resp_fields()

        return flask_restful.marshal(data, cls._resp_fields, envelope)

    @classmethod
    def parse_post_req(cls, req=None):
        if cls._post_parser is None:
            cls._post_parser = reqparse.RequestParser()
            cls._build_post_parser()

        return cls._post_parser.parse_args(req)

    @classmethod
    def parse_patch_req(cls, req=None):
        if cls._patch_parser is None:
            if cls._post_parser is None:
                cls._post_parser = reqparse.RequestParser()
                cls._build_post_parser()
            cls._build_put_parser()

        return cls._patch_parser.parse_args(req)

    @classmethod
    def get_resp_fields(cls):
        if cls._resp_fields is None:
            cls._build_resp_fields()

        return cls._resp_fields
