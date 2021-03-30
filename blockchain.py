import hashlib
import json
from urllib.parse import urlparse
from uuid import uuid4

import requests
from cryptography.fernet import Fernet
from flask import Flask, jsonify, request

from secrets import randbelow


class Blockchain:
    def __init__(self):
        self.chain = []  # blockchain
        self.transaction = []  # transaction to add to block
        self.request = []  # request for book
        self.request_id = []  # id for request
        self.book = []  # encrypted book from node getting request
        self.book_key = []  # private key for encrypted book
        self.nodes = set()  # nodes in network
        self.books = []
        self.new_block(previous_hash='0')
        self.create_nodes(address='http://127.0.0.1:5000')
        self.create_nodes(address='http://127.0.0.1:5001')
        self.create_nodes(address='http://127.0.0.1:5002')
        self.create_nodes(address='http://127.0.0.1:5003')
        self.add_book(book_value=randbelow(10))  # add a random book into each port

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
    def new_transaction(self, req_id, key):
        self.transaction.append({
            'proof': req_id + key
        })
        last_block = self.last_block
        previous_hash = self.hash(last_block)
        self.new_block(previous_hash)

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

    # validate chain by checking previous hashes
    def validate(self):
        previous_block = self.chain[0]
        counter = 1
        while counter < len(self.chain):
            current_block = self.chain[counter]
            previous_hash = self.hash(previous_block)
            if current_block['previous_hash'] != previous_hash:
                return False
            previous_block = current_block
            counter += 1
        return True

    # generating a request
    def new_requests(self, sender_port, receiver_port, book_value):
        # validate previous chain
        network = self.nodes
        for node in network:
            response = requests.get(f'http://{node}/validate')
            if response.status_code != 200:
                return

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
                    check = self.proof(sender_port, receiver_port, value=1)
                    # if proof and consensus is true send key to sender port
                    if check:
                        response = requests.get(f'http://{receiver_port}/get/key')
                        if response.status_code == 200:
                            requests.post(f'http://{sender_port}/set/key', json={
                                'key': response.json()['key']
                            })
                            # after key is sent sender node checks if key is valid by decrypting book
                            # decrypted book should be book_value requested
                            response = requests.get(f'http://{sender_port}/get/key')
                            key = response.json()['key'].encode()
                            response2 = requests.get(f'http://{sender_port}/get/book')
                            encrypted_book = response2.json()['encrypted_book'].encode()
                            f = Fernet(key)
                            book = f.decrypt(encrypted_book).decode()
                            if book == book_value:
                                check = self.proof(sender_port, receiver_port, value=2)
                                # after checking the keys with other nodes, if true, add transaction
                                if check:
                                    network = self.nodes
                                    response = requests.get(f'http://{receiver_port}/get/id')
                                    receiver_id = response.json()['id']
                                    response = requests.get(f'http://{sender_port}/get/key')
                                    sender_key = response.json()['key']
                                    for ports in network:
                                        requests.post(f'http://{ports}/new/transaction', json={
                                            'id': receiver_id,
                                            'key': sender_key
                                        })
                                    requests.post(f'http://{sender_port}/add/book', json={
                                        'book_value': book_value,
                                    })
                                    requests.post(f'http://{receiver_port}/remove/book', json={
                                        'book_value': book_value,
                                    })
                                # if failed remove stored values
                                else:
                                    network = self.nodes
                                    for nodes in network:
                                        requests.get(f'http://{nodes}/reset')
                    # if failed remove stored values
                    else:
                        network = self.nodes
                        for nodes in network:
                            requests.get(f'http://{nodes}/reset')

    # proof to check the matching keys and ids
    def proof(self, sender_port, receiver_port, value):
        # if value = 1 check id, if true id is valid
        if value == 1:
            confirm = 0
            response = requests.get(f'http://{receiver_port}/get/id')
            check_this = response.json()['id']
            network = self.nodes
            for node in network:
                if node != sender_port and node != receiver_port:
                    response = requests.get(f'http://{node}/get/id')
                    compare_this = response.json()['id']
                    # compare the id from receiver_port with other nodes in network
                    if check_this == compare_this:
                        confirm += 1
            check = self.consensus(sender_port, receiver_port, confirm)
            if check:
                return True
        # if value = 2 check keys, if true key is valid
        if value == 2:
            confirm = 0
            response = requests.get(f'http://{sender_port}/get/key')
            check_this = response.json()['key']
            network = self.nodes
            for node in network:
                if node != sender_port and node != receiver_port:
                    response = requests.get(f'http://{node}/get/key')
                    compare_this = response.json()['key']
                    # compare the key from sender_port with other nodes in network
                    if check_this == compare_this:
                        confirm += 1
            check = self.consensus(sender_port, receiver_port, confirm)
            if check:
                return True
        return False

    # check if >50% agrees
    def consensus(self, sender_port, receiver_port, confirm):
        # count all nodes in network but sender and receiver
        # compare if agree is > 50%
        counter = 0
        network = self.nodes
        for node in network:
            if node != sender_port and node != receiver_port:
                counter += 1
        if confirm / counter > 0.5:
            return True
        return False

    # generate book key
    def generate_book_keys(self, book_value):
        # using Fernet to generate keys and encrypt the book
        # decode to send non bytes through network
        key = Fernet.generate_key()
        ubyte_key = key.decode()
        byte_key = Fernet(key)
        encrypted = byte_key.encrypt(book_value.encode())
        ubyte_encrypted = encrypted.decode()
        for i in range(len(self.books)):
            if self.books[i] == book_value:
                self.book.append({'encrypted_book': ubyte_encrypted})
                self.book_key.append({'key': ubyte_key})
                return

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

    # reset
    def reset(self):
        self.transaction = []
        self.request = []
        self.book = []
        self.request_id = []
        self.book_key = []

    # add book
    def add_book(self, book_value):
        self.books.append(book_value)

    # remove book
    def remove_book(self, book_value):
        self.books.remove(book_value)

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


# validation
@app.route('/validate', methods=['GET'])
def validate():
    response = blockchain.validate()
    if response:
        return jsonify(), 200
    return jsonify(), 201


# create the transaction
@app.route('/new/transaction', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['id', 'key']
    if not all(keys in values for keys in required):
        return 'Transaction invalid', 400

    blockchain.new_transaction(values['id'], values['key'])
    response = {'message': "New transaction made"}
    return jsonify(response)


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
    response = {'message': 'Run /get/chain to verify, request added = valid, request not added = invalid and try again'}
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
    }
    return jsonify(response), 200


# get id from request_id list
@app.route('/get/id', methods=['GET'])
def get_id():
    response = {
        'id': blockchain.request_id[0]['id']
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


# reset values
@app.route('/reset', methods=['GET'])
def reset():
    blockchain.reset()
    response = {
        'message': 'Values reset'
    }
    return jsonify(response)


# remove book
@app.route('/remove/book', methods=['POST'])
def remove_book():
    values = request.get_json()
    required = ['book_value']
    if not all(keys in values for keys in required):
        return 'Missing request info', 400
    blockchain.remove_book(values['book_value'])
    response = {'message': "Book removed"}
    return jsonify(response), 201


# append book
@app.route('/add/book', methods=['POST'])
def add_book():
    values = request.get_json()
    required = ['book_value']
    if not all(keys in values for keys in required):
        return 'Missing request info', 400
    blockchain.add_book(values['book_value'])
    response = {'message': "Book added"}
    return jsonify(response), 201


# check books
@app.route('/get/books', methods=['GET'])
def get_books():
    response = {
        'book': blockchain.books
    }
    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen to')
    args = parser.parse_args()
    port = args.port
    app.run(host='127.0.0.1', port=port)
