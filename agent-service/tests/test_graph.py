import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from phonease.app import app, graph, Decision

class GraphTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'OPENAI_API_KEY':'','AGENT_SERVICE_TOKEN':'test-service-token'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.client=TestClient(app)
        self.headers={'Authorization':'Bearer test-service-token'}

    def test_internal_auth_required(self):
        self.assertEqual(self.client.post('/decide',json={'operation':'start'}).status_code,401)

    def test_graph_restores_session_between_requests(self):
        s=self.client.post('/decide',headers=self.headers,json={'operation':'start'}).json()
        s=self.client.post('/decide',headers=self.headers,json={'operation':'turn','session':s,
            'payload':{'text':'yes','event_id':'consent','revision':0}}).json()
        self.assertEqual(s['state'],'collecting')
        s=self.client.post('/decide',headers=self.headers,json={'operation':'turn','session':s,
            'payload':{'text':'Alex Taylor','event_id':'name','revision':1}}).json()
        self.assertEqual(s['pending']['value'],'Alex Taylor')
        s=self.client.post('/decide',headers=self.headers,json={'operation':'turn','session':s,
            'payload':{'text':'yes','event_id':'name-confirm','revision':2}}).json()
        s=self.client.post('/decide',headers=self.headers,json={'operation':'turn','session':s,
            'payload':{'text':'2000','event_id':'answer','revision':3}}).json()
        self.assertEqual(s['pending']['value'],'2000')
        self.assertNotIn('postcode',s['fields'])

    def test_persisted_suppression_is_hydrated(self):
        response=self.client.post('/decide',headers=self.headers,json={'operation':'start','suppressed':True,'payload':{'lead_id':'synthetic-suppressed'}})
        self.assertEqual(response.status_code,400)

    def test_persisted_receipt_is_reused(self):
        seed={'name':'Alex Taylor','postcode':'2000','fuel':'gas','occupancy':'own','moving':False,
            'current_provider':'agl','has_bill':True,'bill_range':'under 200','solar':False,'concession_card':False}
        state=graph.invoke({'request':Decision(operation='start',payload={'seed':seed})})['session']
        state=graph.invoke({'request':Decision(operation='turn',session=state,payload={'text':'yes','event_id':'consent'})})['session']
        receipt={'id':'mock-existing','adapter':'local-mock','payload':{'fields':{'postcode':'2000'}}}
        state=graph.invoke({'request':Decision(operation='turn',session=state,receipt=receipt,payload={'text':'yes','event_id':'submit'})})['session']
        self.assertEqual(state['receipt']['id'],'mock-existing')

    def test_invalid_operation_rejected(self):
        self.assertEqual(self.client.post('/decide',headers=self.headers,json={'operation':'dial'}).status_code,422)
