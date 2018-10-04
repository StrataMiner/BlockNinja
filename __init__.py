# move with BlockNinja
from subprocess import Popen, PIPE, TimeoutExpired, STDOUT
import json
import traceback
import requests
import time
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
import threading
import atexit

class Node:
	def __init__(self, symbol, protocol, nodepath=None, port=None, name=None, password=None, customArgs=None):
		self.symbol = symbol
		self.protocol = protocol
		self.nodepath = nodepath
		self.port = port
		self.name = name
		self.password = password
		self.customArgs = customArgs if customArgs else []
		self.state = False
	def getProcessArgs(self):
		if not self.nodepath:
			return BlockError("no.node.path", "Cannot calculate process arguments because the %s Node object has not been assigned a node path." % self.symbol)
		args = [self.nodepath]
		# -rpcuser wmuser -rpcpassword wmpwd123321 -port %i"
		if self.protocol == "btc":
			args.extend([
				"-server", 
				"-printtoconsole"
			])
			if self.name:
				args.append("-rpcuser=%s" % self.name)
			if self.password:
				args.append("-rpcpassword=%s" % self.password)
			if self.port:
				args.append("-rpcport=%i" % self.port)
		elif self.protocol == "xmr":
			args.append("--log-level=1")
			# "--limit-rate-up=1" # kB/s upload limit
			if self.port:
				args.append("--rpc-bind-port=%i" % self.port)
			if self.name and self.password:
				args.append("--rpc-login=%s:%s" % ( self.name, self.password))
		else:
			self.msgCallback("Unrecognized rpc protocol for %s" % symbol)
			return BlockError("unknown.protocol", "(code 3) Unknown RPC protocol for %s: %s" % (symbol, self.protocol))
		args.extend(self.customArgs)
		return args

	# "state": False,
	# 		"name": "wmuser",
	# 		"password": "wmpwd123321"
	# 	}
	# 	symbolDict = {}
	# 	symbolDict["BTG"] = recursiveUpdate(dict(seed), {
	# 		"node.path": "/home/buck/crypto/btg/bin/bgoldd",
	# 		"rpc.protocol":"btc",
	# 		"port":10456,
	# 		"addnode.list": "https://status.bitcoingold.org/dl.php?format=config", 
	# 		"custom.args": []

class BlockNinja:
	def __init__(self, nodes=None):
		self.id = 0
		self.remoteNodes = set()
		self.nodeProcesses = {}
		self.nodes = {}
		if isinstance(nodes, list):
			for node in nodes:
				self.nodes[node.symbol] = node
		self.threads = []
		self.nodeOn = lambda s: None
		self.nodeOff = lambda s: None
		self.averageBlockTimes = {}
		self.outputPaused = False
		self.msgCallback = lambda s: None    # self.logMessageSignal.emit
		self.outputCallback = lambda s, m: None
		self.xmrTranslator = {
			"getinfo":"get_info", 
			"getblock":"get_block"
		}
		self.prepareRpcCalls()
	def prepareRpcCalls(self):
		callGenerator = self.makeRpcCall
		calls = """AddMultiSigAddress
		AddNode
		AddWitnessAddress
		BackupWallet
		BumpFee
		ClearBanned
		CreateMultiSig
		CreateRawTransaction
		DecodeRawTransaction
		DecodeScript
		DisconnectNode
		DumpPrivKey
		DumpWallet
		EncryptWallet
		EstimateFee
		EstimatePriority
		FundRawTransaction
		Generate
		GenerateToAddress
		GetAccountAddress
		GetAccount
		GetAddedNodeInfo
		GetAddressesByAccount
		GetBalance
		GetBestBlockHash
		GetBlock
		GetBlockChainInfo
		GetBlockCount
		GetBlockHash
		GetBlockHeader
		GetBlockTemplate
		GetChainTips
		GetConnectionCount
		GetDifficulty
		GetGenerate
		GetHashesPerSec
		GetInfo
		GetMemoryInfo
		GetMemPoolAncestors
		GetMemPoolDescendants
		GetMemPoolEntry
		GetMemPoolInfo
		GetMiningInfo
		GetNetTotals
		GetNetworkHashPS
		GetNetworkInfo
		GetNewAddress
		GetPeerInfo
		GetRawChangeAddress
		GetRawMemPool
		GetRawTransaction
		GetReceivedByAccount
		GetReceivedByAddress
		GetTransaction
		GetTxOut
		GetTxOutProof
		GetTxOutSetInfo
		GetUnconfirmedBalance
		GetWalletInfo
		GetWork
		Help
		ImportAddress
		ImportMulti
		ImportPrivKey
		ImportPrunedFunds
		ImportWallet
		KeyPoolRefill
		ListAccounts
		ListAddressGroupings
		ListBanned
		ListLockUnspent
		ListReceivedByAccount
		ListReceivedByAddress
		ListSinceBlock
		ListTransactions
		ListUnspent
		LockUnspent
		Move
		Ping
		PreciousBlock
		PrioritiseTransaction
		PruneBlockChain
		RemovePrunedFunds
		SendFrom
		SendMany
		SendRawTransaction
		SendToAddress
		SetAccount
		SetBan
		SetGenerate
		SetNetworkActive
		SetTxFee
		SignMessage
		SignMessageWithPrivKey
		SignRawTransaction
		Stop
		SubmitBlock
		ValidateAddress
		VerifyChain
		VerifyMessage
		VerifyTxOutProof
		WalletLock
		WalletPassphrase
		WalletPassphraseChange"""
		
		for call in [c.strip() for c in calls.split("\n")]:
			callGenerator(call)
		self.getNethash = self.getNetworkHashPS

		zecCalls = """z_GetBalance
		z_GetTotalBalance
		z_GetNewAddress
		z_ListAddresses
		z_ValidateAddress
		z_ExportViewingKey
		z_ImportViewingKey
		z_ExportKey
		z_ImportKey
		z_ExportWallet
		z_ImportWallet
		z_GetOperationResult
		z_GetOperationStatus
		z_ListOperationIds
		z_ListReceivedByAddress
		z_ListUnspent
		z_SendMany
		z_ShieldCoinbase"""

		for call in [c.strip() for c in zecCalls.split("\n")]:
			lowerString = call.lower()
			pythonedCall = "Z"+call.split("_")[1]
			callGenerator(pythonedCall, lowerString, methodString=lowerString)


		xmrCalls = """get_block_count
		on_get_block_hash
		get_block_template
		submit_block
		get_last_block_header
		get_block_header_by_hash
		get_block_header_by_height
		get_block_headers_range
		get_block
		get_connections
		get_info
		hard_fork_info
		set_bans
		get_bans
		flush_txpool
		get_output_histogram
		get_version
		get_coinbase_tx_sum
		get_fee_estimate
		get_alternate_chains
		relay_tx
		sync_info
		get_txpool_backlog
		get_output_distribution
		get_balance
		get_address
		get_address_index
		create_address
		label_address
		get_accounts
		create_account
		label_account
		get_account_tags
		tag_accounts
		untag_accounts
		set_account_tag_description
		get_height
		transfer
		transfer_split
		sign_transfer
		submit_transfer
		sweep_dust
		sweep_all
		sweep_single
		relay_tx
		store
		get_payments
		get_bulk_payments
		incoming_transfers
		query_key
		make_integrated_address
		split_integrated_address
		stop_wallet
		rescan_blockchain
		set_tx_notes
		get_tx_notes
		set_attribute
		get_attribute
		get_tx_key
		check_tx_key
		get_tx_proof
		check_tx_proof
		get_spend_proof
		check_spend_proof
		get_reserve_proof
		check_reserve_proof
		get_transfers
		get_transfer_by_txid
		sign
		verify
		export_outputs
		import_outputs
		export_key_images
		import_key_images
		make_uri
		parse_uri
		get_address_book
		add_address_book
		delete_address_book
		refresh
		rescan_spent
		start_mining
		stop_mining
		get_languages
		create_wallet
		open_wallet
		close_wallet
		change_wallet_password
		is_multisig
		prepare_multisig
		make_multisig
		export_multisig_info
		import_multisig_info
		finalize_multisig
		sign_multisig
		submit_multisig
		get_version"""

		for call in [c.strip() for c in xmrCalls.split("\n")]:
			callParts = call.split("_")
			cappedMethod = "".join([x.capitalize() for x in callParts])
			lowerMethod = "".join(callParts)
			if not hasattr(self, lowerMethod):
				callGenerator(cappedMethod, call)
			self.xmrTranslator[lowerMethod] = call
	def shutdown(self):
		for symbol, node in self.nodes.items():
			node.state = False
		for symbol, nodeProcess in self.nodeProcesses.items():
			nodeProcess.kill()
		tStart = time.time()
		for symbol, nodeProcess in self.nodeProcesses.items():
			while time.time() - tStart < 20 and nodeProcess.poll() == None:
				time.sleep(0.1)
	def makeThread(self, function, *args, **kwargs):
		thread = threading.Thread(None, function, args=args, kwargs=kwargs)
		thread.start()
		for oldThread in list(self.threads):
			if not oldThread.is_alive():
				self.threads.remove(oldThread)
		self.threads.append(thread)
	def registerNode(self, symbol, protocol, **kwargs):
		self.nodes[symbol] = Node(symbol, protocol, **kwargs)
	def getId(self):
		self.id += 1
		return str(self.id)
	def getRequest(self, method, **params):
		request = {}
		request["method"] = method
		request["params"] = params
		return json.dumps(request)
	def stopNode(self, symbol):
		if symbol in self.nodeProcesses:
			self.nodeProcesses[symbol].kill()
	def startNode(self, symbol):
		if symbol in self.remoteNodes:
			args = self.nodes[symbol].getProcessArgs()
			if args:
				self.msgCallback("You have specified %s as a remote node. Use the following command to start the node from a command prompt.")
				self.msgCallback(" ".join(args))
		if self.nodeIsRunning(symbol):
			return True
		self.makeThread(self.actuallyStartNode, symbol)
		tStart = time.time()
		while time.time() - tStart < 1:
			if self.nodeIsRunning(symbol):
				return True
			time.sleep(0.01)
		return True
	def setNodeRemote(self, symbol):
		self.msgCallback("Setting %s as a remote node" % symbol)
		args = self.nodes[symbol].getProcessArgs()
		if args:
			self.msgCallback("Use the following command to start the node at a command prompt")
			self.msgCallback(" ".join(args))
		self.remoteNodes.add(symbol)
	def actuallyStartNode(self, symbol):
		node = self.nodes[symbol]
		if symbol in self.nodeProcesses:
			nodeProcess = self.nodeProcesses[symbol]
			if nodeProcess.poll() == None:
				node.state = False
				self.msgCallback("Killing %s node" % symbol)
				nodeProcess.kill()
				tStart = time.time()
				itDead = False
				while time.time() - tStart < 30:
					# Wait up to 30 seconds for old process to die
					if nodeProcess.poll() != None:
						itDead = True
						break
					time.sleep(1)
				if not itDead:
					self.msgCallback("Failed to kill %s node. " % symbol)
					return BlockError("zombie.node", "Failed to kill node for %s" % symbol)
		self.msgCallback("Starting node for %s" % symbol)
		node.state = True
		args = self.nodes[symbol].getProcessArgs()
		if not args:
			self.msgCallback("Could not retreive process arguments for %s. " % symbol)
			return BlockError("args.error", "Unable to find calculate process arguments for %s." % symbol)
		nodeProcess = self.nodeProcesses[symbol] = Popen(args, stdout=PIPE, stderr=STDOUT)
		atexit.register(nodeProcess.terminate)
		nodeProcess.peers = 0
		nodeProcess.queuedCalls = []
		lineBuffer = []
		self.makeThread(popenReader, nodeProcess.stdout, lineBuffer)
		self.nodeOn(symbol)
		while True:
			if not node.state:
				break
			if lineBuffer:
				self.outputCallback(symbol, lineBuffer.pop())
			else:
				try:
					retCode = nodeProcess.wait(timeout=1)
					if retCode != None:
						break
				except TimeoutExpired as e:
					continue
				except Exception as e:
					self.msgCallback("Error encountered in node loop: %s \n %s" % (repr(e), traceback.print_tb(e.__traceback__)))
					break
		# Clean up any remaining lines
		for line in lineBuffer:
			self.outputCallback(symbol, line)
		nodeProcess.peers = 0
		nodeProcess.queuedCalls.clear()
		self.nodeOff(symbol)
	def nodeIsRunning(self, symbol):
		if symbol in self.remoteNodes:
			return True
		if symbol not in self.nodeProcesses:
			return BlockError("no.node", "No node process for %s" % symbol)
		nodeProcess = self.nodeProcesses[symbol]
		if nodeProcess.poll() != None:
			return BlockError("dead.node", "%s node appears to be dead" % symbol)
		return True
	###############
	# Base Routines
	###############
	def rpc(self, symbol, method, *listParams, **dictParams):
		print("--running %s" % method)

		nodeStatus = self.nodeIsRunning(symbol)
		if not nodeStatus:
			return nodeStatus

		node = self.nodes[symbol]
		# params["jsonrpc"] = "2.0"
		request = {}
		request["method"] = method
		request["id"] = self.getId()
		request["params"] = listParams if listParams else dictParams if dictParams else []
		headers = {
			'Host': "127.0.0.1",
			'User-Agent': "BlockNinja/0.1",
			'Content-type': 'application/json'
		}
		if node.protocol == "btc":
			auth = HTTPBasicAuth(node.name, node.password)
			url = "http://127.0.0.1:%i" % node.port
		elif node.protocol == "xmr":
			translator = self.xmrTranslator
			if method in translator:
				request["method"] = translator[method]
			auth = HTTPDigestAuth(node.name, node.password)
			url = "http://127.0.0.1:%i/json_rpc" % node.port

		data = json.dumps(request)
		self.msgCallback("-> %s: %s" % (symbol, data))
		try:
			rawResponse = requests.post(
				url,
				data=data,
				headers=headers,
				auth=auth
			)
			response = rawResponse.json()


			if "result" not in response:
				return BlockError("response.format.error", "No result field found in: %s" % rawResponse.text)
			if "status" in response and response["status"] != "OK":
				return BlockError("rcp.not.okay.error", 'RCP response status not "OK". Result: %s' % rawResponse.text)
			if not response["result"]:
				error = response["error"]
				if "code" in error:
					code = error["code"]
					if code == -28:
						return BlockError("node.syncing", "%s node is still syncing" % symbol, response)
				return BlockError("error", "RPC error occured: %r" % error, response)
			return response
		except ValueError as e:
			return BlockError("json.decode.error", "Unable to decode response: %s" % rawResponse.text)
		except Exception as e:
			return BlockError("rpc.exception", "Error encountered for %s request: %s \n %s" % (method, repr(e), traceback.print_tb(e.__traceback__)))
	
	def rpcCallWrapper(self, symbol, method, *args, **kwargs):
		response = self.rpc(symbol, method, *args, **kwargs)
		if not response:
			return response
		return response["result"]
	def makeRpcCall(self, method, *aliases, methodString=None):
		rpcFunc = self.rpcCallWrapper
		lowerMethod = method.lower()
		nippedMethod = method[:1].lower() + method[1:]
		methodString = methodString if methodString else lowerMethod
		f = lambda s, *a, m=methodString, **k: rpcFunc(s,m,*a,**k)
		def f(*a, _m=methodString, _n=self.nodes, **k):
			if not a:
				return BlockError("no.symbol", "%s called without a symbol" % _m)
			s = a[0]
			if s not in _n:
				return BlockError("unknown.symbol", "%s called without an unknown symbol: %s" % (_m, s))
			return rpcFunc(s, _m, *a[1:], **k)
		setattr(self, method, f)
		if hasattr(self, nippedMethod):
			print("--------WARNING: makeRpcCall overwriting existing method: %s" % nippedMethod)
		setattr(self, nippedMethod, f)
		setattr(self, lowerMethod, f)
		for alias in aliases:
			setattr(self, alias, f)
		return f
	# def _setNetHash(self, symbol, nethash):
	# 	self.msgCallback("nethashes for %s set to %r" % (symbol, nethash))
	###################
	# Compound Routines
	###################
	def getBlockByHeight(self, symbol, height):
		protocol = self.nodes[symbol].protocol
		if protocol == "btc":
			return self.getBlockByHeight_btc(symbol, height)
		elif protocol == "xmr":
			return self.getBlockByHeight_xmr(symbol, height)
		else:
			self.msgCallback("Unrecognized rpc protocol for %s" % symbol)
			return BlockError("unknown.protocol", "(code 2) Unknown RPC protocol for %s: %s" % (symbol, protocol))
	def getBlockByHeight_btc(self, symbol, height):
		blockhash = self.getBlockHash(symbol, height)
		if not blockhash:
			return blockhash
		return self.getBlock(symbol, blockhash)
	def getBlockByHeight_xmr(self, symbol, height):
		block = self.getBlockHeaderbyHeight(symbol, height=height)
		# Should probably be translating this to the full block, as returned by getBlock
		if not block:
			return block
		block = block["block_header"]
		block["time"] = block["timestamp"]
		return block
	def getTip(self, symbol):
		protocol = self.nodes[symbol].protocol
		if protocol == "btc":
			return self.getTip_btc(symbol)
		elif protocol == "xmr":
			return self.getTip_xmr(symbol)
		else:
			self.msgCallback("Unrecognized rpc protocol for %s" % symbol)
			return BlockError("unknown.protocol", "(code 3) Unknown RPC protocol for %s: %s" % (symbol, protocol))
	def getTip_btc(self, symbol):
		tips = self.getChainTips(symbol)
		if not tips:
			self.msgCallback("No tips retreived for %s. Error message: %s" % (symbol, tips.errorMessage))
			return tips
		activeTips = [tip for tip in tips if tip["status"] == "active"]
		if not activeTips:
			self.msgCallback("No tips retreived for %s" % symbol)
			return activeTips
		if len(activeTips) > 1:
			self.msgCallback("More than one active tip detected for %s" % symbol)
			return BlockError("multiple.tips", "Multiple tips returned for %s" % symbol)
		activeTip = activeTips[0]
		branchlen, blockhash, height = activeTip["branchlen"], activeTip["hash"], activeTip["height"]
		if branchlen != 0: # btc protocol only
			self.msgCallback("Non-zero branch length detected for %s" % symbol)
			return BlockError("nonzero.branchlen", "Non-zero branch length returned for %s. Something is wrong. " % symbol)
		return self.getBlock(symbol, blockhash)
	def getTip_xmr(self, symbol):
		block = self.getLastBlockHeader(symbol)
		if not block:
			return block
		block = block["block_header"]
		block["time"] = block["timestamp"]
		if block["orphan_status"]:
			self.msgCallback("Orphaned block detected for %s" % symbol)
			return BlockError("orphaned.block.error", "Orphaned block detected for %s" % symbol)
		return block
	def getNethashPts(self, symbol, height, avgLengths=None):
		"""
		Get the nethash avg for the top block at height, for backranges of 1,2,4,8,16,32,64,128
		"""
		protocol = self.nodes[symbol].protocol
		if protocol == "btc":
			return self.getNethashPts_btc(symbol, height, avgLengths)
		elif protocol == "xmr":
			return self.getNethashPts_xmr(symbol, height, avgLengths)
		else:
			self.msgCallback("Unrecognized rpc protocol for %s" % symbol)
			return BlockError("unknown.protocol", "(code 3) Unknown RPC protocol for %s: %s" % (symbol, protocol))
	def getNethashPts_btc(self, symbol, height, avgLengths=None):
		hashrates = {}
		avgLengths = avgLengths if avgLengths else [1,2,4,8,16,32,64,128]
		for blocks in avgLengths:
			nethash = self.getNethash(symbol, blocks, height)
			if not nethash:
				return nethash
			hashrates[blocks] = nethash
		return hashrates
	def getNethashPts_xmr(self, symbol, height, avgLengths=None):
		getinfo = self.getInfo(symbol)
		if not getinfo:
			return getinfo
		target = getinfo["target"]
		height = getinfo["height"]
		headers = self.getBlockHeadersRange(symbol, start_height=height-128, end_height=height-1)
		if not headers:
			return headers
		headers = headers["headers"]
		headers.reverse()
		runningRate = headers[0]["difficulty"]/target
		block = 1
		averages = [runningRate]
		for header in headers[1:]:
			rate = header["difficulty"]/target
			runningRate = (block*runningRate + rate)/(block+1)
			averages.append(runningRate)
			block = block+1
		hashrates = {}
		avgLengths = avgLengths if avgLengths else [2**i for i in range(8)]
		for i in avgLengths:
			hashrates[i] = averages[i-1]
		return hashrates
	def getFirstBlockOfDay(self, symbol, year, month, day, initialGuess=None):
		"""
		An algorithm to find the first block of any day
		"""
		tRequest = time.mktime(time.strptime("%s-%s-%s" % (str(year).zfill(2), str(month).zfill(2), str(day).zfill(2)), "%Y-%m-%d"))
		blockTime = self.averageBlockTimes[symbol] = self.getAverageBlockTime(symbol)
		if not blockTime:
			return blockTime
		if not initialGuess:
			zeroBlock = self.getBlockByHeight(symbol, 0)
			if not zeroBlock:
				return zeroBlock
			tZero = zeroBlock["time"]
			initialGuess = int((tRequest-tZero)/blockTime)
		guess = initialGuess
		tooLow = (0, None)
		tooHigh = (1e12, None)
		def getBlockPeriod(low, high, default=blockTime):
			if not low or not high:
				return default
			return (high["time"]-low["time"])/(high["height"]-low["height"])
		def justifyGuess(g, low, high):
			if low and g <= low["height"]:
				return g+1
			if high and g >= high["height"]:
				return g-1
			return g
		while True:
			block = self.getBlockByHeight(symbol, guess)
			if not block:
				return block
			tBlock = block["time"]
			tGap = tRequest-tBlock
			if tBlock < tRequest:
				lowGuess, lowBlock = tooLow = (guess, block)
				highGuess, highBlock = tooHigh
				if lowGuess + 1 == highGuess:
					return highBlock
				period = getBlockPeriod(lowBlock, highBlock)
				guess = justifyGuess(guess + int(round(tGap/period)), lowBlock, highBlock)
			else:
				lowGuess, lowBlock = tooLow
				highGuess, highBlock = tooHigh = (guess, block)
				if lowGuess + 1 == highGuess:
					return highBlock
				period = getBlockPeriod(lowBlock, highBlock)
				guess = justifyGuess(guess + int(round(tGap/period)), lowBlock, highBlock)
			block = self.getBlockByHeight(symbol, guess)
			if not block:
				return block
		return BlockError("block.search.error", "Unable to locate the first block for %s on %i-%i-%i" % (symbol, year, month, day))

	def getAverageBlockTime(self, symbol, startHeight=None, endHeight=None):
		"""
		Find out the average block time on the given interval. 
		if startHeight(endHeight) are not provided, block 0(chain tip) will be used
		"""
		if symbol in self.averageBlockTimes:
			return self.averageBlockTimes[symbol]
		startHeight = startHeight if startHeight else 0
		endTime = None
		if not endHeight:
			tip = self.getTip(symbol)
			if not tip:
				return tip
			endHeight = tip["height"]
			endTime = tip["time"]
		if endHeight <= startHeight:
			return BlockError("invalid.heights", "the given end height is <= the start height")
		startBlock = self.getBlockByHeight(symbol, startHeight)
		if not startBlock:
			return startBlock
		startTime = startBlock["time"]
		if not endTime:
			endBlock = self.getBlockByHeight(symbol, endHeight)
			if not endBlock:
				return endBlock
			endTime = endBlock["time"]
		bt = self.averageBlockTimes[symbol] = (endTime-startTime)/(endHeight-startHeight)
		return bt

class BlockError:
	def __init__(self, errorType, errorMessage, response=None):
		self.errorType = errorType
		self.errorMessage = errorMessage
		self.response = response
	def __bool__(self):
		return False
	def __repr__(self):
		return("BlockError(%r, %r)" % (self.errorType, self.errorMessage))

def popenReader(streamPointer, lineBuffer):
	while True:
		line = streamPointer.readline()
		if line:
			lineBuffer.append(line.decode('utf-8'))
		else:
			break