import sys
import hashlib
import json

from time import time
from uuid import uuid4

from flask import Flask
from flask.globals import request
from flask.json import jsonify

import requests
from urllib.parse import urlparse

class Blockchain(object):
    difficulty_target = "0000"

    def hash_block(self, block):
        block_encoded = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_encoded).hexdigest()
    
    def __init__(self):
        self.nodes = set()

        self.chain = []
        self.current_transactions = []

        genesis_hash = self.hash_block("genesis_block")

        self.append_block(
            hash_of_previous_block = genesis_hash,
            nonce = self.proof_of_work(0, genesis_hash, [])
        )

    def add_node(self, address):
        parse_url = urlparse(address)
        self.nodes.add(parse_url.netloc)
        print(f'added new node: {parse_url.netloc}')

    def valid_chain(self, chain):
        last_block = chain[0]

        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]

            print(block)

            if block['hash_of_previous_block'] != self.hash_block(last_block):
                print('false 1')
                return False
            
            if not self.valid_proof(
                current_index,
                block['hash_of_previous_block'],
                block['transaction'],
                block['nonce']):
                print('false 2')
                return False

            last_block = block
            current_index += 1

        return True
    
    def update_blockchain(self):
        neighbors = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in neighbors:
            print(f'sync with node: {node}')

            response = requests.get(f'http://{node}/blockchain')

            if response.status_code == 200:
                print('masuk')
                length = response.json()['length']
                chain = response.json()['chain']

                print(f'len{length}')
                print(f'max_len{max_length}')
                print(f'is_valid_chain{self.valid_chain(chain)}')

                if length > max_length and self.valid_chain(chain):
                    print('masuk 2')
                    max_length = length
                    new_chain = chain

                if new_chain:
                    print('masuk 3')
                    self.chain = new_chain
                    return True
                
        return False
    
    def proof_of_work(self, index, hash_of_previous_block, transactions):
        nonce = 0

        while self.valid_proof(index, hash_of_previous_block, transactions, nonce) is False:
            nonce += 1
        return nonce
    
    def valid_proof(self, index, hash_of_previous_block, transactions, nonce):
        content = f'{index}{hash_of_previous_block}{transactions}{nonce}'.encode()
        
        content_hash = hashlib.sha256(content).hexdigest()

        print(content_hash[:len(self.difficulty_target)])
        print(self.difficulty_target)

        return content_hash[:len(self.difficulty_target)] == self.difficulty_target
    
    def append_block(self, nonce, hash_of_previous_block):
        block = {
            'index' : len(self.chain),
            'timestamp' : time(),
            'transaction' : self.current_transactions,
            'nonce' : nonce,
            'hash_of_previous_block' : hash_of_previous_block
        }

        self.current_transactions = []

        self.chain.append(block)
        return block
    
    def add_transaction(self, sender, recepient, amount):
        self.current_transactions.append({
            'sender' : sender,
            'recepient' : recepient,
            'amount' : amount,
        })

        return self.last_block['index'] + 1
    
    @property
    def last_block(self):
        return self.chain[-1]

## app with flask

app = Flask(__name__)

node_identifier = str(uuid4()).replace('-', "")

blockchain = Blockchain()

# routes
@app.route('/blockchain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }

    return jsonify(response), 200

@app.route('/mine', methods=['GET'])
def mine_block():
    blockchain.add_transaction(
        sender='0',
        recepient=node_identifier,
        amount=1
    )

    last_block_hash = blockchain.hash_block(blockchain.last_block)

    index = len(last_block_hash)
    nonce = blockchain.proof_of_work(index, last_block_hash, blockchain.current_transactions)

    block = blockchain.append_block(nonce, last_block_hash)
    response = {
        'message' : "New block has been added to blockchain",
        'index' : block['index'],
        'hash_of_previous_block' : block['hash_of_previous_block'],
        'nonce' : block['nonce'],
        'transaction' : block['transaction']
    }

    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transactions():
    values = request.get_json()

    required_fields = ['sender', 'recepient', 'amount']

    if not all(k in values for k in required_fields):
        return ('Missing required fields'), 400
    
    index = blockchain.add_transaction(
        values['sender'], 
        values['recepient'], 
        values['amount']
    )

    response = {'message': f'Transactions will be added to block {index}'}
    return jsonify(response), 201

@app.route('/nodes/add_nodes', methods=['POST'])
def add_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    
    if nodes is None:
        return ('Error, Missing Node(s) info'), 400
    
    for node in nodes:
        blockchain.add_node(node)

    response = {
        'message': 'New Node has been added successfully',
        'nodes': list(blockchain.nodes)
    }
    
    return jsonify(response), 200

@app.route('/nodes/sync', methods=['GET'])
def sync_nodes():
    updated = blockchain.update_blockchain()
    if updated:
        response = {
            'message': 'Blockchain sync has been updated successfully',
            'blockchain': blockchain.chain
        }
    else:
        response = {
            'message': 'Blockchain already using latest data',
            'blockchain': blockchain.chain
        }

    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(sys.argv[1]))