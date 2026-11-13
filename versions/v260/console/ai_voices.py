"""Bounded named voice catalog shared by the console and Zero worker."""
def voice_id(value):
    if not isinstance(value,str) or not 1<=len(value)<=150 or not all(c.isascii() and (c.isalnum() or c in '_-') for c in value):
        raise ValueError('音色编号无效')
    return value


def catalog(rows,selected=None,*,strict=False):
    if not isinstance(rows,list) or not 1<=len(rows)<=32:raise ValueError('请保留 1～32 个音色')
    result=[];ids=set();names=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'name','id'}:raise ValueError('音色需要名称和 ID')
        identity=voice_id(row['id']);name=row['name']
        if not isinstance(name,str) or not 1<=len(name.strip())<=40 or any(ord(c)<32 for c in name):raise ValueError('音色名称需为 1～40 字')
        name=name.strip()
        if identity in ids or name.casefold() in names:raise ValueError('音色名称和 ID 不能重复')
        ids.add(identity);names.add(name.casefold());result.append({'name':name,'id':identity})
    if selected and selected not in ids:
        if strict:raise ValueError('请先切换到其他音色，再删除当前音色')
        voice_id(selected)
        if len(result)>=32:raise ValueError('音色列表已满')
        name=selected
        result.append({'name':name[:40] if name[:40].casefold() not in names else '当前音色','id':selected})
    return result


def initial(selected):
    return [{'name':'当前音色','id':voice_id(selected)}]


def tools(rows):
    choices=[row['id'] for row in rows]
    names='；'.join(row['name']+'='+row['id'] for row in rows)
    return [
        {'type':'function','name':'list_voices','description':'查看主人已保存的音色名称与 ID。',
         'parameters':{'type':'object','properties':{},'additionalProperties':False}},
        {'type':'function','name':'switch_voice','description':'主人要求更换说话声音时，切换到已保存音色，确认后后续生成的回复使用它。'+names,
         'parameters':{'type':'object','properties':{'voice_id':{'type':'string','enum':choices}},
                       'required':['voice_id'],'additionalProperties':False}}
    ]
