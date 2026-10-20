/** Partial update: role/read-grant edits never include registry_write_tenants.
 * Leaving that attribute out also preserves a concurrent grant change; a
 * read/merge/whole-item Put would silently overwrite it with an older value.
 */
export function userRoleUpdate(username: string, role: string, updatedAt: string,
  email?: string, name?: string, tenants?: string[]) {
  const names: Record<string,string> = {'#role':'role','#updated':'updated_at'};
  const values: Record<string,unknown> = {':role':role,':updated':updatedAt};
  const set = ['#role = :role','#updated = :updated']; const remove: string[] = [];
  for (const [key,value] of Object.entries({email,name})) {
    names[`#${key}`] = key;
    if (value === undefined) remove.push(`#${key}`);
    else { set.push(`#${key} = :${key}`); values[`:${key}`] = value; }
  }
  if (tenants !== undefined) {
    names['#tenants'] = 'tenants';
    if (tenants.length) { set.push('#tenants = :tenants'); values[':tenants'] = tenants; }
    else remove.push('#tenants');
  }
  return {Key:{username}, UpdateExpression:`SET ${set.join(', ')}${remove.length ? ' REMOVE '+remove.join(', ') : ''}`,
    ExpressionAttributeNames:names, ExpressionAttributeValues:values};
}
