==========
BlockNinja
==========
BlockNinja is a multi-protocol Python RPC client. 
BlockNinja has a Pythonized interface for all RPC methods for the Bitcoin and Monero core node protocols, 
as well as the ZCash z\_ variants. Node processes can also be started and stopped with BlockNinja. It accepts 
custom command-line arguments, if desired. 

New methods have also been implemented, e.g. `getBlockByHeight` and `getFirstBlockOfDay`.

BlockNinja can also connect to nodes running elsewhare. This is especially preferred during early application development because BlockNinja
closes all node processes on exit.

Parameters can be passed to individual RPC calls as positional or keyword arguments. If any positional arguments are passed, keyword arguments are ignored and the parameters field of the JSON request will be a list. If only keyword arguments are passed, it will be an object (dictionary).

++++++++++++
Installation
++++++++++++

Manually download into a folder named `blockninja` located either in the same directory as your Python script, or in a directory in your sys.path. Download directly or use `git clone https://github.com/StrataMiner/BlockNinja.git blockninja` from the command line. 

++++++++++++
Bitcoin core
++++++++++++
All Bitcoin core JSON-RPC methods listed at https://bitcoin.org/en/developer-reference#bitcoin-core-apis are implemented

BlockNinja provides aliases for all BTC core methods, so that BlockNinja.GetBlock = BlockNinja.getBlock = BlockNinja.getblock

Additionally, the ZCash payment API is implemented. They are also aliased such that BlockNinja.z_getbalance = BlockNinja.zGetBalance = BlockNinja.zgetbalance = BlockNinja.ZGetBalance

+++++++++++
Monero core
+++++++++++
All Monero core JSON-RPC methods listed at https://getmonero.org/resources/developer-guides/daemon-rpc.html and https://getmonero.org/resources/developer-guides/wallet-rpc.html have been implemented

Aliases are provided for all XMR core methods such that BlockNinja.get_balance = BlockNinja.getBalance = BlockNinja.getbalance = blockNinja.GetBalance

++++++++++++++++
Input and Output
++++++++++++++++
There is no parameter checking. Whatever you give as the arguements(or keyword arguments) is what will be sent in the parameters attribute of the request. 

The returned object is either Python dictionary, or a BlockError object, which has the `errorType` and `errorMessage` properties. A BlockError always evaluates as boolean False, and can be directly `print`'d or `repr`'d.

Use the API documentation websites listed above to see what arguments are required and what to expect in a successful response.

+++++++++++++
Example usage
+++++++++++++

::

	from blockninja import BlockNinja
	import json, time

	symbolDict = {
		"ZEC" : {
			"name": "yourusername",
			"password": "yourpassword",
			"node.path": "/path/to/zcashd",
			"rpc.protocol":"btc",
			"port":10457,
			"custom.args": []
		},
		"ZEN" : {
			"name": "wmuser",
			"password": "wmpwd123321",
			"node.path": "zend",
			"rpc.protocol":"btc",
			"port":10459,
			"addnode.list": None,
			"custom.args": []
		}
	}

	blockNinja = BlockNinja()
	for symbol, info in symbolDict.items():
		blockNinja.registerNode(symbol, 
			protocol = info["rpc.protocol"], 
			nodepath = info["node.path"], 
			port = info["port"], 
			name = info["name"], 
			password = info["password"], 
			customArgs = info["custom.args"]
		)
	symbol = "ZEC"
	blockNinja.setNodeRemote(symbol)
	input("Start the node with the command line arguments above. Then press enter.")

	while True:
		accounts = blockNinja.listAccounts(symbol), indent=4, sort_keys=True)
		if not accounts:
			# if a BlockNinja result evaluates as false, it is a BlockError object
			if accounts.errorType == "node.syncing":
				print("Node still syncing. Trying again in 1 second")
				time.sleep(1)
				continue
			else:
				print("Error fetching accounts: %s" % accounts)
				break
		print(json.dumps(accounts, indent=4, sort_keys=True))
		break