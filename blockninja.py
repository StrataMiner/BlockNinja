# move with BlockNinja
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
import threading

class BlockNinja:
	def __init__(self, symbolInfo, testnet=False):
		self.id = 0
		self.remoteNodes = set()
		self.nodeProcesses = {}
		self.threads = []
		self.nodeOn = lambda s: None
		self.nodeOff = lambda s: None
		self.averageBlockTimes = {}
		self.outputPaused = False
		self.msgCallback = lambda s: None    # self.logMessageSignal.emit
		self.outputCallback = lambda s, m: None
		self.symbolInfo = symbolInfo
		self.xmrTranslator = {
			"getinfo":"get_info", 
			"getblock":"get_block"
		}
		callGenerator = self.makeRpcCall
		self.getNethash = callGenerator("getnetworkhashps")
		self.getPeerInfo = callGenerator("getpeerinfo")
		self.getChainTips = callGenerator("getchaintips")
		self.getBlockChainInfo = callGenerator("getblockchaininfo")
		self.getBlock = callGenerator("getblock")
		self.getBlockHash = callGenerator("getblockhash")
		self.getInfo = callGenerator("getinfo")
		self.getBlockHeaderbyHeight = callGenerator("get_block_header_by_height")
		self.getLastBlockHeader = callGenerator("get_last_block_header")
		self.getBlockHeadersRange = callGenerator("get_block_headers_range")
	def shutdown(self):
		for symbol, info in self.symbolInfo.items():
			info["state"] = False
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
			args = self.getProcessArgs(symbol)
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
		args = self.getProcessArgs(symbol)
		if args:
			self.msgCallback("Use the following command to start the node at a command prompt")
			self.msgCallback(" ".join(args))
		self.remoteNodes.add(symbol)
	def getProcessArgs(self, symbol):
		symbolInfo = self.symbolInfo[symbol]
		args = [symbolInfo["node.path"]]
		# -rpcuser wmuser -rpcpassword wmpwd123321 -port %i"
		if symbolInfo["rpc.protocol"] == "btc":
			args.extend([
				"-server", 
				"-rpcuser=%s" % symbolInfo["name"], 
				"-rpcpassword=%s" % symbolInfo["password"], 
				"-rpcport=%i" % symbolInfo["port"],
				"-printtoconsole"
			])
		elif symbolInfo["rpc.protocol"] == "xmr":
			args.extend([
				"--log-level=1",
				"--rpc-bind-port=%i" % symbolInfo["port"],
				"--rpc-login=%s:%s" % ( symbolInfo["name"], symbolInfo["password"]),
				"--limit-rate-up=1" # kB/s upload limit 
			])
		else:
			self.msgCallback("Unrecognized rpc protocol for %s" % symbol)
			return BlockError("unknown.protocol", "(code 3) Unknown RPC protocol for %s: %s" % (symbol, symbolInfo["rpc.protocol"]))
		args.extend(symbolInfo["custom.args"])
		return args
	def actuallyStartNode(self, symbol):
		symbolInfo = self.symbolInfo[symbol]
		if symbol in self.nodeProcesses:
			nodeProcess = self.nodeProcesses[symbol]
			if nodeProcess.poll() == None:
				symbolInfo["state"] = False
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
		symbolInfo["state"] = True
		args = self.getProcessArgs(symbol)
		if not args:
			self.msgCallback("Could not retreive process arguments for %s. " % symbol)
			return BlockError("args.error", "Unable to find calculate process arguments for %s." % symbol)
		nodeProcess = self.nodeProcesses[symbol] = Popen(args, stdout=PIPE, stderr=STDOUT)
		nodeProcess.peers = 0
		nodeProcess.queuedCalls = []
		lineBuffer = []
		self.makeThread(popenReader, nodeProcess.stdout, lineBuffer)
		self.nodeOn(symbol)
		while True:
			if not symbolInfo["state"]:
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
					self.msgCallback("Error encounter in node loop: %s \n %s" % (repr(e), traceback.print_tb(e.__traceback__)))
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
		nodeStatus = self.nodeIsRunning(symbol)
		if not nodeStatus:
			return nodeStatus

		symbolInfo = self.symbolInfo[symbol]
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
		if symbolInfo["rpc.protocol"] == "btc":
			auth = HTTPBasicAuth(symbolInfo["name"], symbolInfo["password"])
			url = "http://127.0.0.1:%i" % symbolInfo["port"]
		elif symbolInfo["rpc.protocol"] == "xmr":
			translator = self.xmrTranslator
			if method in translator:
				request["method"] = translator[method]
			auth = HTTPDigestAuth(symbolInfo["name"], symbolInfo["password"])
			url = "http://127.0.0.1:%i/json_rpc" % symbolInfo["port"]

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

		# authpair = "%s:%s" % (symbolInfo["name"], symbolInfo["password"])
		# headers['Authorization'] = b"Basic " + base64.b64encode(authpair.encode('utf8'))
		# rawResponse = ""
		# try:
		# 	connection = httplib.HTTPConnection("127.0.0.1", port=symbolInfo["port"], timeout=10)
		# 	connection.request('POST', "/", postdata, headers)
		# 	rawResponse = connection.getresponse().read().decode("utf-8")
		# 	response = json.loads(rawResponse)

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
			return BlockError("rpc.exception", "Error encounter for %s request: %s \n %s" % (method, repr(e), traceback.print_tb(e.__traceback__)))
	
	def rpcCallWrapper(self, symbol, method, *args, **kwargs):
		response = self.rpc(symbol, method, *args, **kwargs)
		if not response:
			return response
		return response["result"]
	def makeRpcCall(self, method):
		rpcFunc = self.rpcCallWrapper
		return lambda s, *a, m=method, **k: rpcFunc(s,m,*a,**k)
	# def _setNetHash(self, symbol, nethash):
	# 	self.msgCallback("nethashes for %s set to %r" % (symbol, nethash))
	###################
	# Compound Routines
	###################
	def getBlockByHeight(self, symbol, height):
		protocol = self.symbolInfo[symbol]["rpc.protocol"]
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
		if not block:
			return block
		block = block["block_header"]
		block["time"] = block["timestamp"]
		return block
	def getTip(self, symbol):
		protocol = self.symbolInfo[symbol]["rpc.protocol"]
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
		protocol = self.symbolInfo[symbol]["rpc.protocol"]
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
			print("Grabbing block %i" % guess)
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
