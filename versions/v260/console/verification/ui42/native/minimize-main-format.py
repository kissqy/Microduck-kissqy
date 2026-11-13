from pathlib import Path
import difflib,re
base=Path('/workspace/scratch/0587ce872ec5/native_work/ui41_padd_before_ui42/src/main.rs').read_text()
path=Path('/workspace/scratch/0587ce872ec5/native_work/Microduck-Source-R17-V186-control57/padd/src/main.rs')
new=path.read_text()
# Strings and comments are indivisible. Restore only text whose lexical tokens
# already equal the UI41 original; additions keep their own formatting.
lex=re.compile(r'//[^\n]*|/\*.*?\*/|r#+".*?"#+|b?"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])\x27|[A-Za-z_]\w*|[0-9][A-Za-z_0-9]*|[^\s]',re.S)
a=list(lex.finditer(base));b=list(lex.finditer(new))
sm=difflib.SequenceMatcher(None,[m.group() for m in a],[m.group() for m in b],autojunk=False)
for block in reversed(sm.get_matching_blocks()):
 if block.size<3:continue
 old=base[a[block.a].start():a[block.a+block.size-1].end()]
 start=b[block.b].start();end=b[block.b+block.size-1].end()
 new=new[:start]+old+new[end:]
assert [m.group() for m in lex.finditer(new)]==[m.group() for m in b], 'must preserve every lexical token'
path.write_text(new)
