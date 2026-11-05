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

from flask_restful import abort
#
from flask import g
from api import base
#
from models import db, Participant, Contact, Endpoint
import views
from services import authentication_service, authorization_service
from views.contact_view import ContactView
from views.generic_auth_obj_view import GenericAuthObjView
from views.participant_view import ParticipantView
from views.participant_view_enriched import ParticipantViewEnriched

# -----------------------------------------------------------------------------------------------------


class ParticipantParentAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /auth/participants/parent
    #
    # Returns the calling endpoint's parent Participant
    #
    def get_parent_participant(self, ):
        participant = Participant.query.filter(Participant.participant_id == g.participant_id).one_or_none()

        resp = ParticipantViewEnriched.generate_resp(participant)
        return views.generate_resp_envelope(resp), 200

    def get(self, ):
        return self.get_parent_participant()

# -----------------------------------------------------------------------------------------------------


class ParticipantAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /auth/participants AND
    # endpoint: /auth/participants/<uuid:participant_uuid>
    #
    # Return a collection all Participants in the system AND
    # Get a single Participant
    #
    def get_participant(self, participant_uuid):
        authorization_service.uudex_admin_or_403()

        if participant_uuid is None:
            participants = Participant.query.all()
        else:
            uuid = str(participant_uuid)
            participants = Participant.query.get_uuid_or_404(uuid)

        resp = ParticipantView.generate_resp(participants)
        return views.generate_resp_envelope(resp), 200

    def get(self, participant_uuid=None):
        return self.get_participant(participant_uuid)

    # patch
    #
    # endpoint: /auth/participants/<uuid:participant_uuid>
    #
    # Update a single Participant
    #
    def update_participant(self, participant_uuid):
        authorization_service.uudex_admin_or_403()

        uuid = str(participant_uuid)
        participant = Participant.query.get_uuid_or_404(uuid)
        args = ParticipantView.parse_patch_req()

        endpoints = Endpoint.query.filter(Endpoint.participant_id == participant.participant_id).all()
        for endpoint in endpoints:
            authentication_service.invalidate_endpoint_cache_entry(endpoint.certificate_dn)

        changes = participant.set_columns(**args)
        if len(changes):
            db.session.commit()

        resp = ParticipantView.generate_resp(participant)
        return views.generate_put_resp_envelope(resp, changes), 200

    def patch(self, participant_uuid):
        return self.update_participant(participant_uuid)

    # delete
    #
    # endpoint: /auth/participants/<uuid:participant_uuid>
    #
    # Delete a single Participant
    #
    def delete_participant(self, participant_uuid):
        authorization_service.uudex_admin_or_403()

        uuid = str(participant_uuid)
        participant = Participant.query.get_uuid_or_404(uuid)

        endpoints = Endpoint.query.filter(Endpoint.participant_id == participant.participant_id).all()
        db.session.delete(participant)

        for endpoint in endpoints:
            authentication_service.invalidate_endpoint_cache_entry(endpoint.certificate_dn)
            authorization_service.remove_user(endpoint.endpoint_uuid)

        db.session.commit()

    def delete(self, participant_uuid):
        self.delete_participant(participant_uuid)
        return '', 204

    # post
    #
    # endpoint: /auth/participants
    #
    # Create a single Participant
    #
    def create_participant(self, ):
        authorization_service.uudex_admin_or_403()

        args = ParticipantView.parse_post_req()
        participant = Participant(**args)
        db.session.add(participant)
        db.session.commit()

        resp = ParticipantView.generate_resp(participant)
        return views.generate_resp_envelope(resp), 200

    def post(self, ):
        return self.create_participant()

# -----------------------------------------------------------------------------------------------------


class ParticipantContactAPI(base.UUDEXResource):

    # post
    #
    # endpoint: /auth/participants/<uuid:participant_uuid>/contacts
    #
    # Create a single Participant Contact
    #
    def create_participant_contact(self, participant_uuid):
        authorization_service.uudex_admin_or_participant_admin_or_403()

        args = ContactView.parse_post_req()

        uuid_participant = args["participant_uuid"]
        participant = Participant.query.get_uuid_or_404(uuid_participant)

        authorization_service.endpoint_in_participant_or_403(participant.participant_id)

        args['participant_id'] = participant.participant_id
        del args['participant_uuid']
        contact = Contact(**args)
        db.session.add(contact)
        db.session.commit()

        resp = ContactView.generate_resp(contact)
        return views.generate_resp_envelope(resp), 200

    def post(self, participant_uuid):
        return self.create_participant_contact(participant_uuid)

    # get
    #
    # endpoint: /auth/participants/<uuid:participant_uuid>/contacts AND
    # endpoint: /auth/participants/<uuid:participant_uuid>/contacts/<int:contact_id>
    #
    # Return a collection of all Contacts for given Participant AND
    # Get a single Contact for the Participant
    #
    # admin_get_all_participant_contacts
    #
    def get_participant_contact(self, participant_uuid, contact_id):
        authorization_service.uudex_admin_or_participant_admin_or_403()

        uuid = str(participant_uuid)
        participant = Participant.query.get_uuid_or_404(uuid)

        authorization_service.endpoint_in_participant_or_403(participant.participant_id)

        if contact_id is None:
            contact = Contact.query.filter(Contact.participant_id == participant.participant_id).all()
        else:
            contact = Contact.query.filter(Contact.contact_id == contact_id).one_or_none()

        if contact is None:
            abort(404, message=f"Not contacts found")

        resp = ContactView.generate_resp(contact)
        return views.generate_resp_envelope(resp), 200

    def get(self, participant_uuid, contact_id=None):
        return self.get_participant_contact(participant_uuid, contact_id)

    # patch
    #
    # endpoint: /auth/participants/<uuid:participant_uuid>/contacts/<int:contact_id>
    #
    # Update a single Contact for the Participant
    #
    def update_participant_contact(self, participant_uuid, contact_id):
        authorization_service.uudex_admin_or_participant_admin_or_403()

        uuid = str(participant_uuid)
        participant = Participant.query.get_uuid_or_404(uuid)

        authorization_service.endpoint_in_participant_or_403(participant.participant_id)

        contact = Contact.query.filter(Contact.contact_id == contact_id).one_or_none()

        if contact is None:
            abort(404, message=f"Contact not found")

        args = ContactView.parse_patch_req()

        changes = contact.set_columns(**args)
        if len(changes):
            db.session.commit()

        resp = ContactView.generate_resp(contact)
        return views.generate_put_resp_envelope(resp, changes), 200

    def patch(self, participant_uuid, contact_id):
        return self.update_participant_contact(participant_uuid, contact_id)

    # delete
    #
    # endpoint: /auth/participants/<uuid:participant_uuid>/contacts/<int:contact_id>
    #
    # Delete a single Contact for the Participant
    #
    def delete_participant_contact(self, participant_uuid, contact_id):
        authorization_service.uudex_admin_or_participant_admin_or_403()

        uuid = str(participant_uuid)
        participant = Participant.query.get_uuid_or_404(uuid)

        authorization_service.endpoint_in_participant_or_403(participant.participant_id)

        contact = Contact.query.filter(Contact.contact_id == contact_id).one_or_none()

        if contact is None:
            abort(404, message=f"Contact not found")

        db.session.delete(contact)
        db.session.commit()

    def delete(self, participant_uuid, contact_id):
        self.delete_participant_contact(participant_uuid, contact_id)
        return '', 204



class ParticipantGroupAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /auth/participants/{participant_uuid}/groups
    #
    # Returns a collection of groups the Participant is a member of
    #
    def get_participant_groups(self, participant_uuid):
        authorization_service.uudex_admin_or_participant_admin_or_403()

        uuid = str(participant_uuid)
        participant = Participant.query.get_uuid_or_404(uuid)
        authorization_service.endpoint_in_participant_or_403(participant.participant_id)

        groups = authorization_service.get_groups_for_participant(uuid)

        resp = GenericAuthObjView.generate_resp(groups)
        return views.generate_resp_envelope(resp), 200

    def get(self, participant_uuid):
        return self.get_participant_groups(participant_uuid)