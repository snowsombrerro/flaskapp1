from flask import Flask, render_template, request, jsonify, redirect, url_for
import aiml
from Bio import Entrez
from Bio import SeqIO
from Bio import ExPASy
from Bio import SwissProt 
import re

app = Flask(__name__)

#create new instance and load the AIML kernel
aiml_kernel = aiml.Kernel() 

def load_aiml():
    #aiml_kernel.learn("templates/b.aiml")
    aiml_kernel.learn("templates/startup.xml")
    aiml_kernel.learn("templates/generic.aiml")
    aiml_kernel.learn("templates/biopython.aiml")

load_aiml()

#deine last_topic variable
last_topic = ""

# define function dictionary to map AIML function names to BioPython function calls
function_dict = {
    "Entrez.esearch": {"module": Entrez, "function_name": "esearch"},
    "Entrez.efetch": {"module": Entrez, "function_name": "efetch"},
    "SeqIO.parse": {"module": SeqIO, "function_name": "parse"},
    "ExPASy.get_sprot_raw": {"module": ExPASy, "function_name": "get_sprot_raw"},
    "SwissProt.read": {"module": SwissProt, "function_name": "read"}
}

# define a function to dynamically call BioPython functions from AIML templates
def call_function(module_name, function_dict, args_str):
    # split the arguments string into a list of arguments
    args = args_str.split(",")
    
    # get the module and function objects based on the module name and function name
    module = function_dict[module_name]["module"]
    function = getattr(module, function_dict[module_name]["function_name"])
    
    # call the function with the arguments and return the result
    result = function(*args)
    return str(result)
    
@app.route("/")
def index():
    return redirect(url_for('interactive_chat'))

@app.route('/interactive-chat')
def interactive_chat():
    return render_template('chat.html')

@app.route('/chat')
def chat():
    global last_topic
    user_input = request.args.get('msg')
    print("User input", user_input)
    bot_response = aiml_kernel.respond(user_input, last_topic)
    print("Bot response", bot_response)
    # check if the response contains an AIML function call
    if "<call>" in bot_response:
        # extract the module name, function name, and arguments from the AIML function call
        match = re.search(r"<call>(.*)\.(.*)\((.*)\)</call>", bot_response)
        module_name = match.group(1)
        function_name = match.group(2)
        args = match.group(3).split(",")
        
        # dynamically call the BioPython function based on the module name and function name
        module = function_dict[module_name]["module"]
        function = getattr(module, function_dict[module_name]["function_name"])
        result = function(*args)
        
        # replace the AIML function call with the result of the BioPython function call
        bot_response = bot_response.replace(match.group(0), str(result))
    
    # check if the user is searching for something
    elif "FETCH SEQUENCE" in user_input.upper():
        last_topic = "fetch_sequence"
        function_name = aiml_kernel.getPredicate("function_name")
        function_args = aiml_kernel.getPredicate("function_args")
        if function_name == "Entrez.esearch":
            Entrez.email = "m3talmark@gmail.com"  # set your email here
            handle = Entrez.esearch(db="pubmed", term=function_args)
            record = Entrez.read(handle)
            count = record["Count"]
            id_list = ",".join(record["IdList"])
            bot_response = aiml_kernel.respond("SEARCH RESULT").replace("{{count}}", str(count)).replace("{{id_list}}", id_list)
    elif last_topic == "search":
        last_topic = ""
        if user_input.isdigit():
            # display the number of sequences requested
            num_sequences = int(user_input)
            # code to retrieve sequences from NCBI goes here
            bot_response = "Here are the first {} sequences:".format(num_sequences)
        else:
            # assume the user is searching for a different gene
            bot_response = aiml_kernel.respond("SEARCH FOR *").replace("*", user_input)
            # check if the user input contains a sequence ID
            match = re.search(r"([A-Z]+\_\d+(\.\d+)?)", user_input)
            if match:
                sequence_id = match.group(1)
                aiml_kernel.setPredicate("sequence_id", sequence_id)
        # add this code to the chat() function after the "SEARCH FOR" block
    elif last_topic == "fetch_sequence":
        last_topic = ""
        print(aiml_kernel.getPredicate("gene_id")) # <-- add this line
        if aiml_kernel.getPredicate("gene_id"):
            gene_id = aiml_kernel.getPredicate("gene_id")
            print("gene_id:", gene_id) # add this line
            if user_input.strip().lower() == "yes":
                print("Entered Yes block")
                 # retrieve the sequence using Entrez.efetch()
                handle = Entrez.efetch(db="nucleotide", id=gene_id, rettype="fasta", retmode="text")
                record = SeqIO.read(handle, "fasta")
                print("Record description: ", record.description)
                print("Record sequence: ", record.seq)
                sequence = str(record.seq)
                print("Sequence: ", sequence) # add this line to check the value of the sequence variable
                bot_response = aiml_kernel.respond("SEQUENCE FOR *").replace("*", record.description)
                aiml_kernel.setPredicate("sequence_id", gene_id)
                aiml_kernel.setPredicate("sequence", sequence)
                bot_response += " " + sequence
            elif user_input.strip().lower() == "no":
                bot_response = "OK, let me know if you need anything else."
                aiml_kernel.setPredicate("gene_id", "") # reset the gene_id predicate
            else:
                bot_response = "Sorry, I didn't understand. Do you want me to retrieve the sequence for {}?".format(gene_id)
        else:
            bot_response = "Sorry, I don't have a gene ID to fetch the sequence for. Please provide a gene ID using the FETCH GENE ID command."
            last_topic = ""

    response = {'bot_response': bot_response}
    return jsonify(response)
if __name__ == '__main__':
    app.run()
