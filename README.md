# Smart Book Management System

![image](https://base.imgix.net/files/base/ebm/mhlnews/image/2019/04/mhlnews_10632_blockchain_2.png?auto=format&fit=crop&h=432&w=768)

## Running
1. Python 3.6+
2. Install pipenv
```
$ pip install pipenv 
```
3. Install requirements  
```
$ pipenv install 
``` 

4. Run the server:
    * `$ python blockchain.py` 
    * `$ python blockchain.py -p 5001`
    * `$ python blockchain.py -p 5002`
    * `$ python blockchain.py -p 5003`
    
## Validation (Proof of works) and Consensus

- Imagine 4 ports 5000,5001,5002,and 5003
- 5000 generates a request id and makes a request to 5001 requesting the book. 
- 5000 sends request id to 5002 and 5003 but not to 5000
- 5000 sends request to 5001 but not 5002 and 5003
- 5001 generates an encrypted key to encrypt the book 5000 requested
- 5001 sends 5002 and 5003 the encrypted key and sends 5000 the encrypted book
- 5000 receives the encrypted book and sends 5001 the request id
- 5001 checks if the request id matches 5002 and 5003 and does the consensus (>50% agrees)
- 5001 sends 5000 the encrypted key
- 5000 decrypts the encrypted book
- 5000 checks if the encrypted key matches 5002 and 5003 and does the consensus (>50% agrees)
- if everything matches then this request would be converted into a transaction and appended into the chain of transaction

- should any case fails, request would be invalid, and a new request would have to be generated 

## Others

- A static network with 4 ports
- After launching each ports, you can add books into each port manually with the /add/book method.
   
   ( This can be ignored, books values will be automatically generated between 0 and 9 inclusive ) 

Sample:  
``` { "book_value": "1" }```

- Valid requests will transfer book ownership 
- The miner is the port requesting the book to prevent any bad actors 
- Requests must follow a specific format, sender_port, receiver_port, and book_value

![Capture](https://user-images.githubusercontent.com/77586278/112199065-284ef680-8be4-11eb-9831-5477cb48d433.PNG)
