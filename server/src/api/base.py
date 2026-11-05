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

import sys
#
import flask_restful
from sqlalchemy.exc import IntegrityError, DatabaseError
#
import config
from app_container import app
from services import authentication_service
from uudex_model_base import db


class UUDEXResource(flask_restful.Resource):

    method_decorators = [authentication_service.authenticate_session]  # applies to all inherited resources

    def dispatch_request(self, *args, **kwargs):
        response = None
        try:
            response = super(UUDEXResource, self).dispatch_request(*args, **kwargs)
        except IntegrityError as ex:  # duplicate key db error
            db.session.rollback()
            app.logger.exception(ex)
            if config.DEBUG:
                raise
            flask_restful.abort(400, message="Data integrity error: Resource already exists")
        except DatabaseError as ex:  # general db error
            ei = sys.exc_info()
            app.logger.exception(ex)
            flask_restful.abort(500)
        except BaseException as ex:
            db.session.rollback()
            ei = sys.exc_info()
            app.logger.exception(ex)
            raise

        return response


class RequestProxy(object):
    json = {}
