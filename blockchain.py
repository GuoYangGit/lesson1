# {
#     # 索引
#     "index": 0,
#     # 时间戳
#     "timestamp": "",
#     "transactions": [
#         {
#             # 交易的发送者
#             "sender": "",
#             # 交易的接受者
#             "recipient": "",
#             # 交易金额
#             "amount": 5,
#         }
#     ],
#     # 工作量证明
#     "proof": "",
#     # 上一个区块的hash值
#     "previous_hash": ""
# }
import hashlib
import json
from argparse import ArgumentParser
from time import time
from urllib.parse import urlparse
from uuid import uuid4

from flask import Flask, jsonify, request
from pip._vendor import requests


class BlockChain:

    def __init__(self):
        # 对应的区块
        self.chain = []
        # 当前的交易信息
        self.current_transactions = []
        # 节点信息
        self.nodes = set()
        # 创建创世纪区块
        self.new_block(proof=100, previous_hash=1)

    # 注册节点
    def register_node(self, address: str):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    # 验证节点的有效性
    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    # 解决冲突
    def resolve_conflicts(self):
        neighbours = self.nodes
        max_length = len(self.chain)
        new_chain = None
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True
        return False

    # 添加一个区块
    def new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.last_block)
        }
        # 清空当前节点中的交易
        self.current_transactions = []
        # 加入到区块链中
        self.chain.append(block)
        return block

    # 添加一个交易
    def new_transaction(self, sender, recipient, amount) -> int:
        self.current_transactions.append(
            {
                "sender": sender,
                "recipient": recipient,
                "amount": amount,
            }
        )
        return self.last_block['index'] + 1

    # 进行hash计算
    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    # 获取区块链的最后一条区块
    @property
    def last_block(self):
        return self.chain[-1]

    # 工作量证明
    def proof_of_work(self, last_proof: int) -> int:
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    # 验证工作量证明
    def valid_proof(self, last_proof: int, proof: int) -> bool:
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[0:4] == "0000"


app = Flask(__name__)
blockChain = BlockChain()

node_identifier = str(uuid4()).replace('-', '')


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ["sender", "recipient", "amount"]

    if values is None:
        return "Missing values", 400
    if not all(k in values for k in required):
        return "Missing values", 400

    index = blockChain.new_transaction(values['sender'],
                                       values['recipient'],
                                       values['amount'])
    response = {
        "msg": f'Transaction will be added to Block {index}'
    }
    return jsonify(response), 201


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockChain.last_block
    last_proof = last_block['proof']
    proof = blockChain.proof_of_work(last_proof)
    blockChain.new_transaction(sender="0",
                               recipient=node_identifier,
                               amount=1)
    block = blockChain.new_block(proof, None)
    response = {
        "msg": "New Block Forged",
        "index": block['index'],
        "transaction": block['transactions'],
        "proof": block['proof'],
        "previous_hash": block['previous_hash']
    }
    return jsonify(response), 200


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockChain.chain,
        'length': len(blockChain.chain)
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get("nodes")
    if nodes is None:
        return "Error:plase supply a valid list of nodes", 400
    for node in nodes:
        blockChain.register_node(node)

    response = {
        "msg": "New nodes have been added",
        "total_nodes": list(blockChain.nodes)
    }
    return jsonify(response), 201


@app.route('/nodes.resolve', methods=['GET'])
def consensus():
    replaced = blockChain.resolve_conflicts()
    if replaced:
        response = {
            "msg": "Our chain was replaced",
            "new_chain": blockChain.chain
        }
    else:
        response = {
            "msg": "Our chain is authoritative",
            "new_chain": blockChain.chain
        }
    return jsonify(response), 200


if __name__ == '__main__':
    parse = ArgumentParser()
    parse.add_argument('-p', '--port', default=5000, type=int, help='port to listen to')
    args = parse.parse_args()
    port = args.port
    app.run(host='0.0.0.0', port=port)
