import binascii
import uuid
from cryptography.fernet import Fernet
import hashlib
import json
from urllib.parse import urlparse
from uuid import uuid4
import requests
from flask import Flask, jsonify, request


class Blockchain:
    def __init__(self):
        self.chain = []  # blockchain
        self.transaction = []  # transaction to add to block
        self.request = []  # request for book
        self.request_id = []  # id for request
        self.book = []  # encrypted book from node getting request
        self.book_key = []  # private key for encrypted book
        self.nodes = set()  # nodes in network

        self.new_block(previous_hash='0')

    # new nodes
    def create_nodes(self, address):
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid')

    # create transaction
    def new_transaction(self):
        self.transaction.append({
            'proof': hashlib.sha256(self.request_id[0]['id'] + self.book_key[0]['key']).hexdigest()
        })
        return self.last_block['index'] + 1

    # creating a new block and clears out all previous requests data
    def new_block(self, previous_hash):
        block = {
            'index': len(self.chain) + 1,
            'transaction': self.transaction,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }
        self.transaction = []
        self.request = []
        self.book = []
        self.request_id = []
        self.book_key = []
        self.chain.append(block)
        return block

    # generating a request
    def new_requests(self, sender_port, receiver_port, book_value):

        # loops through the network of nodes
        # if node is the receiver port send request to it
        # if node is not receiver port send request id to it
        network = self.nodes
        for node in network:
            if node == receiver_port:
                requests.post(f'http://{node}/set/request', json={
                    'sender_port': sender_port,
                    'receiver_port': receiver_port,
                    'book_value': book_value
                })
            elif node != receiver_port and node != sender_port:
                response = requests.get(f'http://{sender_port}/get/id')
                if response.status_code == 200:
                    requests.post(f'http://{node}/request/id', json={
                        'id': response.json()['id']
                    })

        # loops through network of nodes after request if and request has been sent
        # generate an encrypted book and a key from receiver port
        network = self.nodes
        for node in network:
            if node == receiver_port:
                requests.post(f'http://{node}/generate/book', json={
                    'book_value': book_value
                })

        # after generating book and key loop through network
        # if node is the sender port send it the encrypted book
        # all other nodes get the key
        network = self.nodes
        for node in network:
            if node == sender_port:
                response = requests.get(f'http://{receiver_port}/get/book')
                if response.status_code == 200:
                    requests.post(f'http://{node}/set/book', json={
                        'encrypted_book': response.json()['encrypted_book']
                    })
            elif node != sender_port and node != receiver_port:
                response = requests.get(f'http://{receiver_port}/get/key')
                if response.status_code == 200:
                    requests.post(f'http://{node}/set/key', json={
                        'key': response.json()['key']
                    })

        # after sender node gets encrypted book and other nodes get keys
        # sender node sends receiver node the request id
        network = self.nodes
        for node in network:
            if node == receiver_port:
                response = requests.get(f'http://{sender_port}/get/id')
                if response.status_code == 200:
                    requests.post(f'http://{node}/request/id', json={
                        'id': response.json()['id']
                    })

    # generate book key
    def generate_book_keys(self, book_value):
        # using Fernet to generate keys and encrypt the book
        # decode to send non bytes through network
        key = Fernet.generate_key()
        ubyte_key = key.decode()
        byte_key = Fernet(key)
        encrypted = byte_key.encrypt(book_value.encode())
        ubyte_encrypted = encrypted.decode()
        self.book.append({'encrypted_book': ubyte_encrypted})
        self.book_key.append({'key': ubyte_key})

    # adds request into the list
    def set_requests(self, sender_port, receiver_port, book_value):
        self.request.append({
            'sender_port': sender_port,
            'receiver_port': receiver_port,
            'book_value': book_value
        })

    # adds encrypted book into list
    def set_books(self, encrypted_book):
        self.book.append({'encrypted_book': encrypted_book})

    # adds key into list
    def set_keys(self, book_key):
        self.book_key.append({'key': book_key})

    # adds request id into list
    def set_request_ids(self, request_id):
        self.request_id.append({'id': request_id})

    # hashing
    @staticmethod
    def hash(block):
        block_hash = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_hash).hexdigest()

    # get last block
    @property
    def last_block(self):
        return self.chain[-1]


app = Flask(__name__)
node_identifier = str(uuid4()).replace('-', '')
blockchain = Blockchain()


# add new node
@app.route('/new/nodes', methods=['POST'])
def new_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error", 400
    for node in nodes:
        blockchain.create_nodes(node)
    response = {
        'message': "Node created",
        'nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201


# generate request id and a request to be sent
@app.route('/new/request', methods=['POST'])
def new_request():
    values = request.get_json()
    required = ['sender_port', 'receiver_port', 'book_value']
    if not all(keys in values for keys in required):
        return 'Missing request info', 400

    blockchain.set_request_ids(uuid4())
    blockchain.new_requests(values['sender_port'],
                            values['receiver_port'],
                            values['book_value']),
    response = {'message': f"New request for {values['receiver_port']}"}
    return jsonify(response), 201


# set request
@app.route('/set/request', methods=['POST'])
def set_request():
    values = request.get_json()
    required = ['sender_port', 'receiver_port', 'book_value']
    if not all(keys in values for keys in required):
        return 'Missing request info', 400

    blockchain.set_requests(values['sender_port'],
                            values['receiver_port'],
                            values['book_value'])
    response = {'message': f"Request sent to {values['receiver_port']}"}
    return jsonify(response), 201


# set book
@app.route('/set/book', methods=['POST'])
def set_book():
    values = request.get_json()
    required = ['encrypted_book']
    if not all(keys in values for keys in required):
        return 'Missing request info', 400

    blockchain.set_books(values['encrypted_book'])
    response = {'message': "Book sent"}
    return jsonify(response), 200


# set request id by calling set_request_ids
@app.route('/request/id', methods=['POST'])
def set_request_id():
    values = request.get_json()
    required = ['id']
    if not all(keys in values for keys in required):
        return 'Missing request info', 400

    blockchain.set_request_ids(values['id'])
    response = {'message': "Request id sent to other nodes"}
    return jsonify(response), 201


# set book key by calling set_keys method
@app.route('/set/key', methods=['POST'])
def set_key():
    values = request.get_json()
    required = ['key']
    if not all(keys in values for keys in required):
        return 'Missing request info', 400

    blockchain.set_keys(values['key'])
    response = {'message': "Request key sent to other nodes"}
    return jsonify(response), 201


# generate book by calling generate_book_key method
@app.route('/generate/book', methods=['POST'])
def generate_book():
    values = request.get_json()
    required = ['book_value']
    if not all(keys in values for keys in required):
        return 'Missing request info', 400

    blockchain.generate_book_keys(values['book_value'])
    response = {'message': "Book and keys generated"}
    return jsonify(response), 201


# get the encrypted book from book list
@app.route('/get/book', methods=['GET'])
def get_book():
    response = {
        'encrypted_book': blockchain.book[0]['encrypted_book']
    }
    return jsonify(response), 200


# get key from key list
@app.route('/get/key', methods=['GET'])
def get_key():
    response = {
        'key': blockchain.book_key[0]['key']
        # 'check_key': blockchain.book_key[1]['key']
    }
    return jsonify(response), 200


# get id from request_id list
@app.route('/get/id', methods=['GET'])
def get_id():
    response = {
        'id': blockchain.request_id[0]['id']
        # 'check_id': blockchain.request_id[1]['id']
    }
    return jsonify(response), 200


# get request from request list
@app.route('/get/request', methods=['GET'])
def get_request():
    response = {
        'sender_port': blockchain.request[0]['sender_port'],
        'receiver_port': blockchain.request[0]['receiver_port'],
        'book_value': blockchain.request[0]['book_value']
    }
    return jsonify(response), 200


# get chain
@app.route('/get/chain', methods=['GET'])
def get_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen to')
    args = parser.parse_args()
    port = args.port
    app.run(host='127.0.0.1', port=port)
