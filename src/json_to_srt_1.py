import json
import boto3
import re
import codecs
import time
import math
import os

s3 = boto3.resource('s3')

def newPhrase():
    return { 'start_time': '', 'end_time': '', 'words' : [] }
    
def getTimeCode(seconds):
# ....t_hund = int(seconds % 1 * 1000)
# ....t_seconds = int( seconds )
# ....t_secs = ((float( t_seconds) / 60) % 1) * 60
# ....t_mins = int( t_seconds / 60 )
# ....return str( "%02d:%02d:%02d,%03d" % (00, t_mins, int(t_secs), t_hund ))
    (frac, whole) = math.modf(seconds)
    frac = frac * 1000
    return str('%s,%03d' % (time.strftime('%H:%M:%S',time.gmtime(whole)), frac))
    
def writeTranscriptToSRT( transcript, sourceLangCode, srtFileName):
    print( "==> Creating SRT from transcript")
    phrases = getPhrasesFromTranscript( transcript )
    writeSRT( phrases, srtFileName)
    
def getPhrasesFromTranscript( transcript ):

	ts = json.loads( transcript )
	items = ts['results']['items']
	#print( items )

	phrase =  newPhrase()
	phrases = []
	nPhrase = True
	x = 0
	c = 0
	lastEndTime = ""

	print("==> Creating phrases from transcript...")

	for item in items:

		if nPhrase == True:
			if item["type"] == "pronunciation":
				phrase["start_time"] = getTimeCode( float(item["start_time"]) )
				nPhrase = False
				lastEndTime =  getTimeCode( float(item["end_time"]) )
			c+= 1
		else:	
			if item["type"] == "pronunciation":
				phrase["end_time"] = getTimeCode( float(item["end_time"]) )
				
		phrase["words"].append(item['alternatives'][0]["content"])
		x += 1
		
		if x == 10:
			#print c, phrase
			phrases.append(phrase)
			phrase = newPhrase()
			nPhrase = True
			x = 0
	 
	if(len(phrase["words"]) > 0):
		if phrase['end_time'] == '':
            		phrase['end_time'] = lastEndTime
		phrases.append(phrase)	
				
	return phrases
	
def writeSRT( phrases, filename):
    print ("==> Writing phrases to disk...")

    e = codecs.open(filename, "w+", "utf-8")
    x = 1
    
    for phrase in phrases:

        length = len(phrase["words"])
        
        e.write( str(x) + "\n" )
        x += 1
        
        e.write( phrase["start_time"] + " --> " + phrase["end_time"] + "\n" )
                    
        out = getPhraseText( phrase )

        e.write(out + "\n\n" )
        

        #print out
        
    e.close()
    
def getPhraseText( phrase ):

    length = len(phrase["words"])
        
    out = ""
    for i in range( 0, length ):
        if re.match( '[a-zA-Z0-9]', phrase["words"][i]):
            if i > 0:
                out += " " + phrase["words"][i]
            else:
                out += phrase["words"][i]
        else:
            out += phrase["words"][i]
            
    return out

def lambda_handler(event, context):  
    print('## ENVIRONMENT VARIABLES')
    print(os.environ)
    print('## EVENT')
    print(event)
    
    for record in event['Records']:
        file_bucket = record['s3']['bucket']['name']
        file_name = record['s3']['object']['key']
        
        s3.Bucket(file_bucket).download_file(file_name, '/tmp/input.json')
        
        input_file = '/tmp/input.json'
        output_file = '/tmp/output.srt'

        with open(input_file, "r") as f:
            data = writeTranscriptToSRT(f.read(), 'en', output_file)
        file_name=file_name.replace("_Output.json", "")
        object = s3.Object('srt-output', file_name +"_Output.srt")
        with open('/tmp/output.srt', 'rb') as f:
            object.put(Body = f)

def test_locally():  
    input_file = 'El_Jeremias_Spanish_feature_2398.json'
    output_file = 'output.srt'

    with open(input_file, "r") as f:
        writeTranscriptToSRT(f.read(), 'en', output_file)

if __name__ == '__main__':
    test_locally()