import hashlib
import json
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request
from textwrap import dedent
from urllib.parse import urlparse
import requests


class Blockchain(object):


    '''
    Class is responsible for managing the chain
    stores transactions and helper methods for adding new blocks to
    the chain

    '''

    def __init__(self):

        # holds the ledger of transactions
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        
        # creates the genesis block
        self.new_block(previous_hash=1,proof=1)

    def register_node(self, address):
        '''
        append new node to list of nodes
        :param address: <str> Address of node
        :return: None
        '''         
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self,chain):
        '''
        determines if a given chain is valid
        :param chain: <list> a blockchain
        :return: <bool> True if the blockchain is valid, False otherwise
        '''

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-------\n")

            #check if hash of block is corrent
            if block['previous_hash'] != self.hash(last_block):
                return False

            # validate proof of work
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index +=1
        
        return True


    def resolve_conflicts(self):
        '''
        Consensus Algorithm amoung nodes, resolves conflicts by
        replaces a blocks chain with the longest
        valid one in the network of nodes
        :return: <bool> True if current block's chain was replaced, False otherwise
        '''

        neighbours = self.nodes
        new_chains = None
        
        # returns length of current blocks chain
        max_length = len(self.chain)

        # pull and verify all nodes in network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # check if length of neighbour node is longer than current block
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

            # replace current chain if longer valid chain is found in another node 
            if new_chain:
                self.chain = new_chain
                return True

            return False 


    def new_block(self, proof, previous_hash=None):
        '''
        Creates a new block and adds it to the chain 
        :param proof: <int>
        :param previous_hash: (Optional) <str> Hash of the previous block
        return <dict> the new block

        '''

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash':previous_hash or self.hash(self.chain[-1])
        }
        
        # reset the current list of transactions
        self.current_transactions = []

        # adds the new block to the chain       
        self.chain.append(block)
        return block


    def new_transaction(self,sender, recipient, amount):
        ''' 
        creates a new transaction for the next mined block
        :param sender: <str> Address of the sender
        :param recipient: <str> Address of the recipient
        :param amount: <int> Amount
        :returns: <int> the index of the block that will hold this transaction
        '''    

        self.current_transactions.append({
           'sender': sender,
           'recipient': recipient,
           'amount':amount
        })    
        
        return self.last_block['index'] + 1



    @staticmethod
    def hash(block):
        '''
        Creates a SHA-256 hash of a block
        :param block: <dict> Block
        :return: <str>

        '''
        # uses encode and haslib to generate a unique hash to identify a given block
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        # returns the last block in the chain
       return self.chain[-1]

    def proof_of_work(self, last_proof):
        '''
        a simple proof of work algorithm
        Find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
        p is the previous proof, and p' is the new proof
        :param last_proof: <int>
        :return: <int>

        '''
        proof = 0
        # add 1 until a valid proof is found  
        while self.valid_proof(last_proof, proof) == False:
            proof += 1
        # returns proof once found 
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        '''
        will return true if hash(last_proof, proof) contain 4 leading zeros 
        :param last_proof: <int> previous proof
        :param proof: <int> Current Proof
        :return: <bool> True if correct, False if not.    
        '''

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == '0000'

# instantiate node
app = Flask(__name__)

# generates a gloablly unique address for the node 
node_identifier = str(uuid4()).replace('-', '')

# create an instance of the blockchain class
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    
    # get last block of chain
    last_block = blockchain.last_block
    # get last proof from block
    last_proof = last_block['proof']
    
    # calculates a new proof of work for the block
    proof = blockchain.proof_of_work(last_proof)

    # sample coin is generated after proof of work is calculated
    # sender 0 signifies a new coin
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1
    )

    # obtains hash of last block in the chain 
    previous_hash = blockchain.hash(last_block)
    # create new Block by adding it to the chain with the previous hash and proof of work
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200



@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    
    # holds data from POST 
    values = request.get_json(force=True)

    if values == None:
        return "Requests body returning None", 400

    # Check if required fields are in POST request
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Mising Values', 400

    # creates a new transaction block
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])    

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201



@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods =['POST'])
def register_nodes():
    values = request.get_json(force=True)

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'new nodes have been added',
        'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201

@app.route('/nodes/resolve',methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:

        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        } 
    
    return jsonify(response), 200



if __name__ == '__main__':
    app.run(host ='0.0.0.0', port=5000)


