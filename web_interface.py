"""Local browser demo. Run: python web_interface.py (no dependencies)."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from SimpleAssembler import assemble, AssemblyError
from SimpleSimulator import Machine, SimulationError, parse_machine_code

EXAMPLES = {
    'Add and store': 'var result\nmov R0 $12\nmov R1 $8\nadd R0 R1 R2\nst R2 result\nld R3 result\nhlt',
    'Sum 1 to 5': 'var total\nmov R0 $1\nmov R1 $5\nmov R2 $0\nmov R3 $1\nloop: add R2 R0 R2\nadd R0 R3 R0\ncmp R0 R1\njgt done\njmp loop\ndone: st R2 total\nhlt',
    'Overflow and FLAGS': 'mov R0 $255\nls R0 $8\nmov R1 $255\nadd R0 R1 R0\nmov R1 $1\nadd R0 R1 R2\nmov R3 FLAGS\nhlt',
    'Floating point': 'movf R0 $1.5\nmovf R1 $2.25\naddf R0 R1 R2\nsubf R1 R0 R3\nhlt',
}

HTML = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Assembler Simulator</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0c1222;color:#e8edf8;font:15px system-ui}main{max-width:1350px;margin:auto;padding:28px}h1{margin:0 0 6px;font-size:30px}p{color:#a9b8d1}button,select,input{font:inherit;border:1px solid #425273;border-radius:6px;background:#243454;color:#fff;padding:9px;cursor:pointer}button:hover{background:#35517c}button:disabled{opacity:.4;cursor:default}.primary{background:#17695f}.grid{display:grid;grid-template-columns:1fr 1.4fr;gap:18px}.card{background:#141e33;border:1px solid #2b3956;border-radius:12px;padding:18px;margin-top:18px}textarea{width:100%;min-height:330px;resize:vertical;background:#0c1425;color:#d8efff;border:1px solid #425273;border-radius:6px;padding:14px;font:15px/1.6 monospace;tab-size:4}.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}.scroll{overflow:auto;max-height:310px}table{border-collapse:collapse;width:100%;font:13px monospace}td,th{padding:8px;text-align:left;border-bottom:1px solid #2b3956;white-space:nowrap}th{position:sticky;top:0;background:#1c2942}.active{background:#27585d}.changed{color:#70f2c1}#message{white-space:pre-wrap;color:#88e5cd}#message.error{color:#ffadad}input[type=range]{flex:1;min-width:100px}h2{font-size:18px;margin:0 0 12px}.badge{color:#93f0cf}a{color:#9bceff}label{display:inline-flex;gap:6px;align-items:center}@media(max-width:850px){.grid{grid-template-columns:1fr}main{padding:16px}}
</style>
<main><h1>Assembler Simulator</h1><p>Write assembly → assemble 16-bit instructions → explore registers, flags and memory after each cycle.</p>
<div class="grid"><section><div class="card"><h2>Program</h2><div class="toolbar"><label>Example <select id="examples"></select></label><button id="load">Load</button><label>Input <select id="mode"><option value="assembly">Assembly</option><option value="binary">Machine code</option></select></label></div>
<textarea id="source" spellcheck="false" aria-label="Program source"></textarea><div class="toolbar"><button class="primary" id="assemble">Assemble</button><button class="primary" id="run">Assemble & run</button><button id="download" disabled>Download binary</button></div><div id="message" role="status">Ready.</div>
<details><summary>Syntax help</summary><p>Three registers: <code>add SOURCE SOURCE DEST</code> (also sub, mul, xor, or, and, addf, subf).<br>Move: <code>mov DEST $INTEGER</code> or <code>mov DEST SOURCE</code>.<br>Invert: <code>not SOURCE DEST</code>. Divide: <code>div SOURCE SOURCE</code> → quotient R0, remainder R1.<br>Memory: <code>var name</code> before instructions, then <code>st R0 name</code> / <code>ld R1 name</code>.<br>Branch: <code>cmp R0 R1</code>, followed by jlt/jgt/je LABEL; jmp is unconditional.<br>Use R0–R6; FLAGS can only be copied with mov. End with hlt. Comments start with #.</p></details></div>
<div class="card"><h2>Machine code</h2><div class="scroll"><table><thead><tr><th>Address</th><th>16-bit word</th><th>Source</th></tr></thead><tbody id="code"></tbody></table></div></div></section>
<section><div class="card"><h2>Execution <span id="status" class="badge"></span></h2><div class="toolbar"><button id="reset" disabled>Reset</button><button id="back" disabled>Back</button><button id="step" disabled>Step</button><button id="play" disabled>Play</button><input id="seek" type="range" min="0" max="0" value="0" aria-label="Execution cycle"><span id="cycle">Cycle 0</span></div><p id="current">Assemble and run a program to start.</p><table><thead><tr><th>Register</th><th>Decimal / raw</th><th>Binary</th><th>Mini-float view</th></tr></thead><tbody id="registers"></tbody></table><p id="flags">FLAGS: V=0 L=0 G=0 E=0</p></div>
<div class="card"><h2>Memory <small>(256 words)</small></h2><p id="access">Includes instructions followed by variables. Changes are highlighted.</p><div class="scroll"><table><thead><tr><th>Address</th><th>Label / variable</th><th>Decimal</th><th>Binary</th></tr></thead><tbody id="memory"></tbody></table></div></div></section></div></main>
<script>
const $=id=>document.getElementById(id);let data=null,position=0,timer=null,words=[];
function cell(row,text){const c=document.createElement('td');c.textContent=text;row.append(c);return c}
function stop(){if(timer)clearInterval(timer);timer=null;$('play').textContent='Play'}
function clearResult(){stop();data=null;words=[];position=0;for(const id of ['code','memory','registers'])$(id).replaceChildren();for(const id of ['reset','back','step','play','download'])$(id).disabled=true;$('seek').max=0;$('seek').value=0;$('cycle').textContent='Cycle 0';$('status').textContent='';$('current').textContent='Assemble and run a program to start.';$('flags').textContent='FLAGS: V=0 L=0 G=0 E=0';$('access').textContent='Includes instructions followed by variables. Changes are highlighted.'}
function draw(){if(!data)return;const s=position?data.trace[position-1]:null,prev=position>1?data.trace[position-2].registers:Array(8).fill(0),regs=s?s.registers:Array(8).fill(0),mem=data.initial_memory.slice();for(let i=0;i<position;i++){const a=data.trace[i].memory_access;if(a&&a.kind==='write')mem[a.address]=a.value}
$('registers').replaceChildren();regs.forEach((v,i)=>{const row=document.createElement('tr');if(v!==prev[i])row.className='changed';cell(row,i===7?'FLAGS':'R'+i);cell(row,v);cell(row,v.toString(2).padStart(16,'0'));cell(row,i===7?'—':((1+(v&31)/32)*2**((v>>5)&7)).toString());$('registers').append(row)});
$('memory').replaceChildren();mem.forEach((v,i)=>{const row=document.createElement('tr');if(s&&s.memory_access&&s.memory_access.address===i)row.className='active';cell(row,i.toString().padStart(3,'0'));cell(row,Object.entries({...data.labels,...data.variables}).filter(([k,a])=>a===i).map(([k])=>k).join(', '));cell(row,v);cell(row,v.toString(2).padStart(16,'0'));$('memory').append(row)});
const f=regs[7];$('flags').textContent=`FLAGS: V=${(f>>3)&1} L=${(f>>2)&1} G=${(f>>1)&1} E=${f&1}`;$('cycle').textContent=`Cycle ${position} / ${data.trace.length}`;$('seek').value=position;$('status').textContent=s&&s.halted?'Halted':position===data.trace.length?'Stopped':'Ready';$('current').textContent=s?`Executed PC ${s.pc}: ${data.instructions[s.pc]||s.operation} → next PC ${s.next_pc}`:'Initial state: PC 0; all registers zero.';$('access').textContent=s&&s.memory_access?`${s.memory_access.kind} memory[${s.memory_access.address}] = ${s.memory_access.value}`:'No data-memory access this cycle.';
for(const row of $('code').children)row.className=s&&Number(row.dataset.pc)===s.pc?'active':'';$('back').disabled=position===0;$('step').disabled=position>=data.trace.length;$('play').disabled=position>=data.trace.length;if(position>=data.trace.length)stop()}
async function execute(action){clearResult();$('message').className='';$('message').textContent='Processing…';try{const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:$('source').value,mode:$('mode').value,action})});const result=await response.json();if(!response.ok)throw Error(result.error);data=result;words=result.words;$('code').replaceChildren();words.forEach((w,i)=>{const row=document.createElement('tr');row.dataset.pc=i;cell(row,i);cell(row,w);cell(row,result.instructions[i]||'');$('code').append(row)});$('download').disabled=false;$('message').textContent=result.error||`${words.length} instruction(s), ${Object.keys(result.variables).length} variable(s). ${result.trace.length} cycle(s) simulated.`;if(result.error)$('message').className='error';$('seek').max=result.trace.length;$('reset').disabled=false;draw()}catch(e){$('message').className='error';$('message').textContent=e.message}}
$('assemble').onclick=()=>execute('assemble');$('run').onclick=()=>execute('run');$('step').onclick=()=>{stop();position++;draw()};$('back').onclick=()=>{stop();position--;draw()};$('reset').onclick=()=>{stop();position=0;draw()};$('seek').oninput=()=>{stop();position=Number($('seek').value);draw()};$('play').onclick=()=>{if(timer){stop();return}$('play').textContent='Pause';timer=setInterval(()=>{position++;draw()},450)};$('source').oninput=clearResult;$('mode').onchange=()=>{clearResult();$('run').textContent=$('mode').value==='binary'?'Run machine code':'Assemble & run'};
$('download').onclick=()=>{const url=URL.createObjectURL(new Blob([words.join('\n')+'\n'],{type:'text/plain'}));const a=document.createElement('a');a.href=url;a.download='program.bin';a.click();URL.revokeObjectURL(url)};
fetch('/api/examples').then(r=>r.json()).then(examples=>{for(const name of Object.keys(examples)){const o=document.createElement('option');o.textContent=name;$('examples').append(o)}function load(){clearResult();$('source').value=examples[$('examples').value];$('mode').value='assembly';$('run').textContent='Assemble & run';$('message').textContent='Ready.'}$('load').onclick=load;load()});
</script></html>'''


def evaluate(payload):
    source = payload.get('source')
    if not isinstance(source, str):
        raise ValueError('source must be text')
    if len(source) > 65536:
        raise ValueError('Source is too large (maximum 64 KiB)')
    mode, action = payload.get('mode', 'assembly'), payload.get('action', 'run')
    if mode not in ('assembly', 'binary') or action not in ('assemble', 'run'):
        raise ValueError('Invalid input mode or action')
    if mode == 'assembly':
        assembly = assemble(source)
        words, instructions = assembly.words, assembly.instructions
        labels, variables = assembly.labels, assembly.variables
    else:
        words, instructions = parse_machine_code(source), []
        labels, variables = {}, {}
    machine = Machine(words)
    result = dict(words=words, instructions=instructions, labels=labels,
                  variables=variables, initial_memory=machine.memory.copy(), trace=[])
    if action == 'run':
        try:
            while not machine.halted:
                if len(result['trace']) >= 2000:
                    raise SimulationError('Stopped at 2000 cycles; possible infinite loop. Partial trace is available.')
                result['trace'].append(machine.step())
        except SimulationError as exc:
            result['error'] = str(exc)
    return result


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, kind='application/json'):
        encoded = body.encode('utf-8') if isinstance(body, str) else json.dumps(body).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', kind + '; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == '/':
            self.respond(200, HTML, 'text/html')
        elif self.path == '/api/examples':
            self.respond(200, EXAMPLES)
        else:
            self.respond(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path != '/api/run':
            self.respond(404, {'error': 'Not found'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 131072:
                raise ValueError('Request must contain at most 128 KiB of JSON')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Expected a JSON object')
            self.respond(200, evaluate(payload))
        except (ValueError, AssemblyError, SimulationError) as exc:
            self.respond(400, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Open http://127.0.0.1:{args.port} in your browser. Press Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
