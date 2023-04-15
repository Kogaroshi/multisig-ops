from brownie import Contract, network
from helpers.addresses import r
from web3 import Web3
import json
import requests
from dotmap import DotMap
from prettytable import PrettyTable
import os

### This script was built for BIP-177.  It's an example of how to map gauges to pool names and addresses
### In this case it pulls in tx builder json files that contain gauge adds and removes through the authorizer and builds a
### table includes function, guage, pool address and gauge name.
def dicts_to_table_string(dict_list, header=None):
    table = PrettyTable(header)
    for dict_ in dict_list:
        table.add_row(list(dict_.values()))
    return str(table)

INFURA_KEY  = os.getenv('WEB3_INFURA_PROJECT_ID')
w3_by_chain = {
    "mainnet": Web3(Web3.HTTPProvider(f"https://mainnet.infura.io/v3/{INFURA_KEY}")),
    "arbitrum": Web3(Web3.HTTPProvider(f"https://arbitrum-mainnet.infura.io/v3/{INFURA_KEY}")),
    "optimism": Web3(Web3.HTTPProvider(f"https://optimism-rpc.gateway.pokt.network")),
    "polygon": Web3(Web3.HTTPProvider(f"https://polygon-mainnet.infura.io/v3/{INFURA_KEY}")),
    "gnosis": Web3(Web3.HTTPProvider(f"https://rpc.gnosischain.com/")),
    "goerli": Web3(Web3.HTTPProvider(f"https://goerli.infura.io/v3/{INFURA_KEY}")),
}

def main(tx_builder_json="../../../BIPs/BIP-242 thru 250.json"):
    outputs = []
    with open(tx_builder_json, "r") as json_data:
        payload = json.load(json_data)
    tx_list = payload["transactions"]
    authorizer = Contract(r.balancer.authorizer_adapter)
    gauge_controller = Contract(r.balancer.gauge_controller)
    vault = Contract(r.balancer.vault)
    for transaction in tx_list:
        if transaction["contractMethod"]["name"] != "performAction":
            continue ## Not an Authorizer tx
        authorizer_target_contract = Web3.toChecksumAddress(transaction["contractInputsValues"]["target"])
        if authorizer_target_contract == gauge_controller:
            (command, inputs) = gauge_controller.decode_input(transaction["contractInputsValues"]["data"])
        else: # Kills are called directly on gauges, so assuming a json with gauge adds disables if it's not a gauge control it's a gauge.
            (command, inputs) = Contract(authorizer_target_contract).decode_input(transaction["contractInputsValues"]["data"])

        #print(command)
        #print(inputs)
        if len(inputs) == 0: ## Is a gauge kill
            gauge_type = "NA"
            gauge_address = transaction["contractInputsValues"]["target"]
        else:
            gauge_address = inputs[0]
            gauge_type = inputs[1]

        #if type(gauge_type) != int or gauge_type == 2: ## 2 is mainnet gauge
        gauge = Contract(gauge_address)
        print(f"processing {gauge}")
        pool_token_list = []
        #print(gauge.selectors.values())
        fxSelectorToChain = {
            "getTotalBridgeCost": "arbitrum",
            "getPolygonBridge": "polygon",
            "getArbitrumBridge": "arbitrum",
            "getGnosisBridge": "gnosis",
            "getOptimismBridge": "optimism"
        }

        fingerprintFx = list(set(gauge.selectors.values()).intersection(list(fxSelectorToChain.keys())))
        if len(fingerprintFx) > 0:  ## Is sidechain
            l2 = fxSelectorToChain[fingerprintFx[0]]
            recipient = gauge.getRecipient()
            chain = f"{l2}-main"
            network.disconnect()
            network.connect(chain)
            l2hop1=Contract(recipient)
            l2hop2=Contract(l2hop1.reward_receiver())
            pool_name = l2hop2.name()
            lp_token = l2hop2.lp_token()
            network.disconnect()
            network.connect("mainnet")
        elif "name" not in gauge.selectors.values():
            recipient = Contract(gauge.getRecipient())
            escrow = Contract(recipient.getVotingEscrow())
            pool_name =  escrow.name()
            lp_token = Contract(escrow.token()).name()
        else:
            pool_name = gauge.name()
            lp_token = gauge.lp_token()

        outputs.append({
            "function": command,
            "gauge_address": gauge_address,
            "gauge_type": gauge_type,
            "pool_name": pool_name,
            "lp_token": lp_token
        })
        #else:
        #    print(f"skipping non-mainnet gauge {gauge_address}")
        #    outputs.append({
        #        "function": command,
        #        "gauge_address": gauge_address,
        #        "gauge_type": gauge_type,
        #        "pool_name": "NA",
        #        "lp_token": "NA"
        #    })


    print(dicts_to_table_string(outputs, outputs[0].keys()))


