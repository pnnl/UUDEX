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

from collections import OrderedDict

from flask_restful import abort


def extract_attr_from_exception(e, default_value, attr="message"):
    if hasattr(e, 'data') and attr in e.data:
        if type(e.data[attr]) is dict:
            message_list = ["{0}: {1}".format(x, y) for (x, y) in e.data[attr].items()]
            message = " , ".join(message_list)
        else:
            message = e.data[attr]
    else:
        message = default_value

    return message

#
# TODO: This is gross! - we need a better way to do this
#
def nest_flat_list(flat_list, layout):

    output = []
    level_state = []
    for level in range(len(layout)):
        level_state.append(dict())
        level_state[level]["prev_value"] = None
        level_state[level]["current_record"] = None
        level_state[level]["current_list"] = None

    for item in flat_list:
        for level in range(0, len(layout)):
            current_layout_record = layout[level]
            is_last_level = level == len(layout) - 1

            if level_state[level]["prev_value"] is None or item[current_layout_record["key_idx"]] != level_state[level]["prev_value"] or is_last_level:

                is_root_level = level == 0
                is_multi_col = current_layout_record["end_idx"] - current_layout_record["start_idx"] > 0

                if level_state[level]["current_record"] is not None and is_root_level:
                    output.append(level_state[level]["current_record"])

                if is_multi_col:
                    current_record = OrderedDict()
                    for i in range(current_layout_record["start_idx"], current_layout_record["end_idx"] + 1):
                        key = item.keys()[i]
                        current_record[key] = item[i]
                    level_state[level]["current_record"] = current_record
                else:
                    current_record = item[current_layout_record["start_idx"]]

                if not is_last_level:
                    level_state[level]["prev_value"] = item[current_layout_record["key_idx"]]
                    current_record[layout[level + 1]["key_name"]] = list()
                    level_state[level]["current_list"] = current_record[layout[level + 1]["key_name"]]

                if not is_root_level:
                    prev_record_list = level_state[level - 1]["current_list"]
                    prev_record_list.append(current_record)

    if len(output) == 0:
        return level_state[0]["current_record"]  # only 1 record
    else:
        output.append(level_state[0]["current_record"])
        return output


def get_code_id_from_value(entity, col, value) -> tuple:
    filters = {col: value}
    res = entity.query.filter_by(**filters).one_or_none()

    if res is None:
        abort(404, code=404, message=f"{col} not found")

    col_name = [m.key for m in entity.__table__.columns][0]
    code_value = getattr(res, col_name)

    return col_name, code_value

