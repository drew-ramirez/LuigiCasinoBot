"""One-document wallet purchases, durable ownership and revisioned equipment.

A successful purchase updates balance, inventory and its receipt in the same
Mongo write. Rendering and Discord delivery happen after that commit. Existing
accounts need no migration: default cosmetics are virtual, permanent ownership.
"""
from copy import deepcopy
import re
import time

from cosmetics.catalog import CATALOG, OFFERS, Appearance, CosmeticCatalog, appearance, equipped_ids, owned_ids, public_profile, validate_catalog

REQUEST=re.compile(r'^[A-Za-z0-9_-]{1,80}$')


class CosmeticsStore:
    def __init__(self,collection=None,ensure_user=None,*,items=CATALOG,offers=OFFERS):
        if collection is None:
            from economy.EconomyManager import EconomyManager
            collection=EconomyManager.COLLECTION
            ensure_user=ensure_user or EconomyManager.ensure_user
        validate_catalog(items,offers)
        self.collection,self.ensure_user=collection,ensure_user
        self.catalog=CosmeticCatalog(items,offers)
        self.items,self.offers=self.catalog.items,self.catalog.offers

    def _record(self,user_id,username='Unknown'):
        if type(user_id) is not int or user_id<=0:raise ValueError('A valid player is required')
        record=self.ensure_user(user_id,username) if self.ensure_user else self.collection.find_one({'user_id':user_id})
        if not isinstance(record,dict) or record.get('user_id')!=user_id or '_id' not in record:
            raise ValueError('An existing casino account is required')
        return record

    @staticmethod
    def _state(record,*,writing=False):
        state=record.get('cosmetics')
        if state is None and 'cosmetics' not in record:
            return {'schema_version':1,'revision':0,'owned':[],'equipped':{},'receipts':{}}
        valid=(isinstance(state,dict) and state.get('schema_version')==1
               and type(state.get('revision')) is int and state['revision']>=0
               and isinstance(state.get('owned'),list) and all(isinstance(i,str) for i in state['owned'])
               and isinstance(state.get('equipped'),dict) and isinstance(state.get('receipts'),dict))
        if not valid:
            if writing:raise ValueError('This cosmetic inventory version cannot be updated safely')
            return {'schema_version':1,'revision':0,'owned':[],'equipped':{},'receipts':{}}
        return deepcopy(state)

    def _snapshot(self,record):
        state=self._state(record)
        public_record={**record,'cosmetics':state}
        owned=sorted(owned_ids(state))
        return {'user_id':record['user_id'],'balance':record.get('balance',0),'revision':state['revision'],
                'owned':owned,'equipped':equipped_ids(public_record,self.items),
                'appearance':appearance(public_record,self.items),
                'animations_enabled':(record.get('animations_enabled') is None or bool(record['animations_enabled'])),
                'profile':public_profile(record)}

    def get(self,user_id,username='Unknown'):
        return self._snapshot(self._record(user_id,username))

    def appearance_for(self,user_id):
        # Read-only rendering lookup must not create wallets or expose documents.
        if type(user_id) is not int or user_id<=0:return Appearance()
        record=self.collection.find_one({'user_id':user_id})
        return appearance(record,self.items) if isinstance(record,dict) else Appearance()

    @staticmethod
    def _query(record,state,cost=0):
        query={'_id':record['_id']}
        if cost>0:query['balance']={'$gte':cost}
        if 'cosmetics' not in record:query['cosmetics']={'$exists':False}
        else:
            query['cosmetics.revision']=state['revision']
            query['cosmetics.schema_version']=1
        return query

    def _purchase_offer(self, record, state, offer_id, quote_id, request_id):
        receipt=state['receipts'].get(request_id)
        if receipt:
            if receipt.get('offer_id')!=offer_id or receipt.get('quote_id')!=quote_id:
                raise ValueError('This confirmation already belongs to another purchase')
            return 'replayed', None
        offer=self.offers.get(offer_id)
        if offer is None:raise ValueError('This pack is no longer available')
        if quote_id!=offer.quote_id:raise ValueError('This pack changed; review its current contents and price')
        owned=owned_ids(state)
        if set(offer.item_ids)<=owned:return 'already_owned', None
        if set(offer.item_ids)&owned:raise ValueError('Some pack items are already owned; no coins were spent')
        if record.get('balance',0)<offer.price:raise ValueError('Insufficient casino coins')
        return None, offer

    def _commit_purchase(self, record, state, offer, quote_id, request_id):
        query=self._query(record,state,offer.price)
        state['owned']=sorted(set(state['owned'])|set(offer.item_ids))
        state['revision']+=1
        state['receipts'][request_id]={'offer_id':offer.id,'quote_id':quote_id,'price':offer.price,
            'item_ids':list(offer.item_ids),'purchased_at':int(time.time())}
        return self.collection.find_one_and_update(query,
            {'$set':{'cosmetics':state},'$inc':{'balance':-offer.price,'cosmetics_spent':offer.price}},return_document=True)

    def purchase(self,user_id,offer_id,quote_id,request_id,username='Unknown'):
        if not isinstance(offer_id,str) or not isinstance(quote_id,str):
            raise ValueError('Invalid pack confirmation')
        if not isinstance(request_id,str) or not REQUEST.fullmatch(request_id):
            raise ValueError('Invalid purchase request')
        for _ in range(8):
            record=self._record(user_id,username)
            state=self._state(record,writing=True)
            status,offer=self._purchase_offer(record,state,offer_id,quote_id,request_id)
            if status:return {'status':status,'snapshot':self._snapshot(record)}
            updated=self._commit_purchase(record,state,offer,quote_id,request_id)
            if updated is not None:return {'status':'purchased','snapshot':self._snapshot(updated)}
        raise ValueError('Your collection changed; refresh and try again')

    def equip(self,user_id,item_id,revision,username='Unknown'):
        if type(revision) is not int or revision<0:raise ValueError('Invalid collection revision')
        item=self.items.get(item_id)
        if item is None:raise ValueError('Unknown cosmetic')
        record=self._record(user_id,username)
        state=self._state(record,writing=True)
        if revision!=state['revision']:return self._snapshot(record),False
        if item_id not in owned_ids(state):raise ValueError('You do not own this cosmetic')
        if equipped_ids(record,self.items)[item.slot]==item_id:return self._snapshot(record),True
        state['equipped'][item.slot]=item_id;state['revision']+=1
        updated=self.collection.find_one_and_update(self._query(record,self._state(record)),
            {'$set':{'cosmetics':state}},return_document=True)
        if updated is None:return self.get(user_id,username),False
        return self._snapshot(updated),True
