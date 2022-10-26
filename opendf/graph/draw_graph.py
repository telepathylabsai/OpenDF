"""
Functions to draw the graph using graphviz.
"""

# First version scratch


from opendf.graph.nodes.node import Node
from opendf.exceptions import parse_node_exception
import re
from graphviz import Digraph
from opendf.defs import *
from opendf.graph.node_factory import NodeFactory
from opendf.utils.utils import to_list

logger = logging.getLogger(__name__)

node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()

CHAR_COLON = '&#58;'
CHAR_LT = '&#60;'
CHAR_GT = '&#62;'
CHAR_AND = '&#38;'


color_sat = 1.2  # color saturation - 1.0 default. higher values make drawing more lively


# ################################ helper functions ################################

# graphviz does not like some characters - replace by char codes. there must be some lib for this...
def fix_chars(s):
    t = s
    if '&' in s: # in case we call this multiple times on the same string - don't replace '&' again
        t = ''
        l = len(s)-4
        for i,c in enumerate(s):
            if c=='&':
                if i<l and s[i+1]=='#' and s[i+3]==';':
                    t += c
                else:
                    t += CHAR_AND
            else:
                t+=c
    return re.sub('>', CHAR_GT, re.sub('<', CHAR_LT, re.sub(':', CHAR_COLON, t)))


def split_len(s, n):
    if len(s) < 1.1 * n:
        return [s]
    i = 0
    t = []
    while i < len(s):
        t.append(s[i:min(i + n, len(s))])
        i += n
    return t


def split_sexp(s):
    tt = s
    t = tt.split('\n')
    t.append('')
    return "<" + '<BR ALIGN="LEFT"/>'.join(t) + '>'


def gen_err_msg(ss, w=20, hints=None, sugg=None, fnt_sz=15):
    s = fix_chars(ss)
    msg = ''
    c = ''
    for j in s.split():
        ii = split_len(j, w)
        for i in ii:
            if i != 'NL':
                c = c + i
            if len(c) > w or i == 'NL':
                msg = msg + c + '<BR/>'
                c = ''
            else:
                c = c + ' '
    if len(c) > 0:
        msg = msg + c
    if environment_definitions.show_hints and hints:
        msg = msg + '<BR/>{' + ','.join(['<BR/>'.join([i for j in to_list(hints) for i in split_len(str(j), 40)])]) + '}'
    if environment_definitions.show_sugg and sugg:
        msg = msg + '<BR/><BR/>Suggestions:<BR/>' + \
              ','.join(['<BR/>'.join([i for j in sugg for i in split_len(j, 40)])]) + '<BR/>'

    ms = msg.strip()
    if MSG_COL in ms and len(ms) == len(MSG_COL) + 7:  # problem with empty message - add space
        ms += ' '
    if not ms:
        ms = ' ? '
    return "< <font point-size='%d'>" % fnt_sz + ms + '</font> >'


def gen_split_NL(s, fntsz=25):
    s = fix_chars(s)
    t = s.split(' NL ')
    if len(t) > 1:
        s = '<BR/>'.join(t)
    return "< <font point-size='%d'>" % fntsz + s + '</font> >'


def gen_exc_msg(e, w=20):
    s, nd, hints, sg = parse_node_exception(e)
    return gen_err_msg(s, w, hints, sg)


def get_lab_name(s, nd):
    if DEBUG_MSG in s:
        return gen_err_msg(s.split(DEBUG_MSG)[1], 50)
    asg = [i for i in nd.context.assign if nd.context.assign[i] == nd] \
        if nd.context and environment_definitions.show_assign and nd in nd.context.assign.values() else []
    ass = ','.join(asg)
    if ass:
        col = saturate('#0088ff')
        ass = "<font color='%s'>" % col + ass + ":</font>"  # + ' '
    summ = False
    if s.startswith('summarize'):
        s = s[len('summarize'):]
        summ = True
    n, b = s.split('=') if s.count('=')==1 else (s, '?') if '=' not in s else (s.split('=')[0], ':'.join(s.split('=')[1:]))
    # if summ:
    #     b = re.sub('_', ' ', re.sub('/', '<BR/>', b))
    tgs = [i for i in list(nd.tags.keys()) if TAG_NO_SHOW not in i] if environment_definitions.show_tags else []
    if nd.constraint_level > 0:
        tgs = [t for t in tgs if t not in nd.type_tags and TAG_NO_SHOW not in t] if environment_definitions.show_tags \
            else []
    tg = [i if nd.tags[i] == '' else '%s=%s' % (i, nd.tags[i]) for i in tgs] if environment_definitions.show_tags \
        else []
    ptg = []
    if True or nd.constraint_level == 0:
        if nd.mutable:
            ptg.append('Mut')
        if nd.detach:
            ptg.append('/')
        if nd.res_block:
            tg.append('|')
    if nd.hide:  # show also for constraints
        ptg.append('/')
    if nd.constr_obj_view == VIEW.INT:
        ptg.append(CHAR_LT)  # '<'
    stg = "<font point-size='10'><sup>%s</sup></font>" % ','.join(tg) if tg else ''
    sptg = "<font point-size='12'><sup>%s</sup></font>" % ','.join(ptg) if ptg else ''
    snum = "<font point-size='9'><sub>%s</sub></font>" % n if environment_definitions.show_node_id else ''
    b = fix_chars(b)
    if summ:
        b = re.sub('_', ' ', re.sub('/', '<BR/>', b))
    lb = '<' + ass + stg + b + sptg + snum + '>'
    return lb


def saturate(c, fact=None):
    """
    Makes graph colors more lively.
    """
    fact = color_sat * fact if fact else color_sat
    if isinstance(c, str) and len(c) == 7 and c[0] == '#' and fact != 1.0:
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:], 16)
        a = (r + g + b) // 3
        [rr, gg, bb] = [max(0, min(255, int(a + (i - a) * fact))) for i in [r, g, b]]
        return '#' + ''.join(['%02x' % i for i in [rr, gg, bb]])
    else:
        return c


# TODO: do we still need this?
def reform_msg(s):
    return 'summarize' + re.sub('_NL_', '/',
                                re.sub(' ', '_', re.sub(',', '-', re.sub(':', CHAR_COLON, re.sub('&', CHAR_AND, s)))))


def strip_col(s, col):
    if MSG_COL in s:
        ss = s.split(MSG_COL)
        col = ss[1][:7]
        s = ss[0] + ss[1][7:]
    return s, saturate(col)


# is the node a BD node which is connected only to other DB node?
# depending on flag hide_internal_db, remove these from the drawing (save screen real estate)
def db_internal(n):
    if NODE_COLOR_DB in n.tags:
        for (nm, nd) in n.outputs:
            if NODE_COLOR_DB not in nd.tags:
                return False
        for nd in n.res_out:
            if NODE_COLOR_DB not in nd.tags:
                return False
        return True
    return False


def do_draw_graph(ff, node_names, goals, excp=None, mesg=None, id_off=0, subgraphs=None):
    excp = excp if excp else []
    ex_nodes = [(parse_node_exception(e)[1], 'ExceptionNode##%d' % i, gen_exc_msg(e)) for (i, e) in enumerate(excp)]
    if ex_nodes and environment_definitions.show_last_exc_per_node:
        ex_nodes = list({x[0]:x for x in ex_nodes}.values())
    mesg = mesg if mesg else []
    #msg_nodes = {n: ('MessageNode##%d' % i, gen_err_msg(m, fnt_sz=20)) for (i, (n, m)) in enumerate(mesg)}
    msg_nodes = {m.node: ('MessageNode##%d' % i, gen_err_msg(m.text, fnt_sz=20)) for (i, m) in enumerate(mesg)}
    expln = None
    if excp:
        msg, nd, _, _ = parse_node_exception(excp[-1])
        expl = nd.explain(msg=msg)
        if expl:
            expln = gen_err_msg(' NL '.join(expl), w=60, fnt_sz=20)
            logger.info('E1=%s\nE2=%s', expl, expln)
    node_cols, outline_cols = {}, {}
    for n in node_names:
        node_cols[n], outline_cols[n] = 'lightgray', 'black'
        for t in n.tags:
            if t.startswith(OUTLINE_COLOR):
                outline_cols[n] = saturate(t[len(OUTLINE_COLOR):])
            if t.startswith(NODE_COLOR):
                node_cols[n] = t[len(NODE_COLOR):]
            if DB_NODE_TAG in t:
                node_cols[n] = '#77bb77'
            node_cols[n] = saturate(node_cols[n])

    hide_extra = node_fact.leaf_types if environment_definitions.hide_extra_base else []

    f = ff
    fntsz = ''
    # nodes
    for xnd, xnm, xmsg in ex_nodes:
        mm, col = strip_col(xmsg, '#ff6666')
        f.attr('node', shape='ellipse', style='filled', color=col, fontcolor='', fillcolor='')
        f.node(xnm, label=mm)
    if expln and environment_definitions.show_explain:
        mm, col = strip_col(expln, '#66ff66')
        f.attr('node', shape='rectangle', style='filled', color=col, fontcolor='', fillcolor='')
        f.node('explain_node', label=mm)
    for n in msg_nodes:  # add a message pointing at node where it occurred
        mm, col = strip_col(msg_nodes[n][1], '#aaaaff')
        f.attr('node', shape='ellipse', style='filled', color=col, fontcolor='', fillcolor='')
        f.node(msg_nodes[n][0], label=mm)

    if not environment_definitions.sep_graphs or not subgraphs:
        subgraphs = [list(node_names.keys())] + [ex_nodes] + [list(msg_nodes.values())]

    for ig, subg in enumerate(subgraphs):
        with ff.subgraph(name='cluster_%d' % ig) as f:
            for n in subg:
                if n in node_names:
                    style = 'filled' if n.evaluated else ''
                    fillcolor = node_cols[n] if n.evaluated else ''
                    lb = get_lab_name(node_names[n], n)
                    ncol, col = node_cols[n], outline_cols[n]
                    style = style + (',' if style else '') + 'bold,rounded' if DB_NODE_TAG in n.tags else style
                    if n.typename() in environment_definitions.summarize_typenames + hide_extra and \
                            n.constraint_level == 0:
                        f.attr('node', shape='rectangle', style=style, color=col, fontsize=fntsz, fontcolor='',
                               fillcolor=fillcolor)
                    elif n.is_modifier():
                        stl = style + (',' if style else '') + 'rounded'
                        f.attr('node', shape='rectangle', color=col, fontsize=fntsz, style=stl, fontcolor='',
                               fillcolor=fillcolor)
                    elif n.is_operator():
                        f.attr('node', shape='box3d', color=col, fontsize=fntsz, style=style, fontcolor='',
                               fillcolor=fillcolor)
                    elif n.constraint_level > 2:  # Node???() or higher - currently not in use
                        f.attr('node', shape='pentagon', color=col, fontsize=fntsz, style=style, fontcolor='',
                               fillcolor=fillcolor)
                    elif n.constraint_level > 1:  # Node??()
                        stl = style + (',' if style else '') + 'diagonals'
                        f.attr('node', shape='diamond', color=col, fontsize=fntsz, style=stl, fontcolor='',
                               fillcolor=fillcolor)
                    elif n.constraint_level > 0:  # Node?()
                        f.attr('node', shape='diamond', color=col, fontsize=fntsz, style=style, fontcolor='',
                               fillcolor=fillcolor)
                    elif type(n) != n.out_type:  # n is a function node
                        f.attr('node', shape='ellipse', color=col, fontsize=fntsz, style=style, fontcolor='',
                               fillcolor=fillcolor)
                    else:
                        f.attr('node', shape='rectangle', style=style, color=col, fontsize=fntsz, fontcolor='',
                               fillcolor=fillcolor)
                    f.node(node_names[n], label=lb)

            if environment_definitions.show_goal_id:
                for i, g in enumerate(goals):  # add numbered circles pointing to goals
                    if g in subg:
                        col = '#ffffcc' if g.typename() == 'revise' else '#ffff00'
                        col = '#ccffff' if g in g.context.other_goals else col
                        col = saturate(col)
                        f.attr('node', shape='circle', style='filled', color=col, fontsize='20.0', fontcolor='',
                               fillcolor='')
                        f.node('##' + str(i + 1 + id_off), label=str(i + 1 + id_off))
            if environment_definitions.show_tags and not environment_definitions.show_config:
                i = 0
                cl = saturate('#880088')
                for n in subg:
                    for t in n.tags:
                        if TAG_NO_SHOW not in t:
                            f.attr('node', shape='egg', style='', color=cl, fontsize=fntsz, fontcolor=cl, fillcolor='')
                            f.node('tagXXX%d' % i, label='%s=%s' % (t, n.tags[t]) if n.tags[t] != '' else t)
                            f.attr('edge', color=cl, style='', arrowhead='', fontsize=fntsz, fontcolor=cl, fillcolor='')
                            f.edge('tagXXX%d' % i, node_names[n])
                            i += 1
            for xnd, xnm, xmsg in ex_nodes:  # add edge for error messages
                if xnd in subg:
                    f.attr('edge', color=saturate('#ff6666'), fontsize='8.0')
                    f.edge(node_names[xnd], xnm)
            if expln and environment_definitions.show_explain and ex_nodes:
                xnd, xnm, xmsg = ex_nodes[-1]
                if xnd in subg:
                    f.attr('edge', color=saturate('#ff6666'), fontsize='8.0')
                    f.edge(node_names[xnd], 'explain_node')
            for n in msg_nodes:  # add edge for error messages
                if n in subg:
                    f.attr('edge', color=saturate('#aaaaff'), fontsize='8.0')
                    f.edge(node_names[n], msg_nodes[n][0])

    f = ff
    # edges
    for n in node_names:
        if n.typename() not in environment_definitions.summarize_typenames + hide_extra:
            for nm in n.inputs:
                inp = n.inputs[nm]
                if inp in node_names:
                    lab = n.signature.pretty_name(nm) if environment_definitions.show_alias else nm
                    # show alias if it exists

                    lab = lab if n.not_operator() else ''
                    lab = '' if lab == posname(1) and posname(2) not in n.inputs else lab
                    if environment_definitions.show_view:
                        lab = lab + "<font point-size='9'><sub>%s</sub></font>" % (
                            'i' if n.view_mode[nm] == VIEW.INT else 'e')
                    if environment_definitions.show_prm_tags and nm in n.signature and n.signature[nm].prmtags:
                        lab = lab + "<font point-size='10'><sup>%s</sup></font>" % ','.join(n.signature[nm].prmtags)
                    lab = '<' + lab + '>' if lab else lab
                    f.attr('edge', color='black', style='', arrowhead='', fontsize=fntsz, fontcolor='', fillcolor='')
                    f.edge(node_names[inp], node_names[n], label=lab)
            if n.result is not None and n.result != n and n.result in node_names:
                f.attr('edge', color='blue', style='dashed', arrowhead='inv', fontsize=fntsz, fontcolor='',
                       fillcolor='')
                f.edge(node_names[n.result], node_names[n])
            if environment_definitions.show_detach:
                for (nm, nd) in n.detached_nodes:
                    lab = nm
                    lab = '' if lab == posname(1) and posname(2) not in n.inputs else lab
                    f.attr('edge', color='red', style='dashed', arrowhead='', fontsize=fntsz, fontcolor='red',
                           fillcolor='')
                    f.edge(node_names[nd], node_names[n], label=lab)
        if environment_definitions.show_dup and n.dup_of is not None and n in node_names and n.dup_of in node_names:
            f.attr('edge', color='green', style='dashed', arrowhead='', fontsize=fntsz, fontcolor='red', fillcolor='')
            f.edge(node_names[n.dup_of], node_names[n])

    if environment_definitions.show_goal_id:
        for i, g in enumerate(goals):  # add numbered circles pointing to goals
            f.attr('edge', color=saturate('#00cccc'), style='', arrowhead='none', fontsize=fntsz, fontcolor='',
                   fillcolor='')
            f.edge(node_names[g], '##' + str(i + 1 + id_off))
            if environment_definitions.show_goal_link and i > 0:
                f.attr('edge', color=saturate('#ffff88'), style='', arrowhead='none', fontsize=fntsz, fontcolor='',
                       fillcolor='')
                f.edge('##' + str(i + id_off), '##' + str(i + 1 + id_off))


def draw_graphs(goals, ex, msg, id=0, ok=True, sexp=None, txt=None, simp=None, f=None):
    hide_extra = node_fact.leaf_types if environment_definitions.hide_extra_base else []
    id_off = 0
    if environment_definitions.show_only_n > 0:
        id_off = len(goals)
        goals = goals[-min(len(goals), environment_definitions.show_only_n):]
        id_off -= len(goals)
    nodes = Node.collect_nodes(goals, follow_res=True, follow_detached=environment_definitions.show_detach,
                               summarize=environment_definitions.summarize_typenames + hide_extra)
    subgraphs = []
    if environment_definitions.sep_graphs:
        ss = []
        for ii, i in enumerate(goals):
            nn = Node.collect_nodes([i], follow_res=True, follow_detached=environment_definitions.show_detach,
                                    summarize=environment_definitions.summarize_typenames + hide_extra)
            logger.info('==>> Group %d - got %d nodes', ii, len(nn))
            mm = [i for i in nn if i not in ss]
            ss += mm
            subgraphs.append(mm)
    if environment_definitions.hide_internal_db:
        nodes = [i for i in nodes if not db_internal(i)]
    node_names = Node.assign_node_names(nodes, summarize=environment_definitions.summarize_typenames + hide_extra)
    if environment_definitions.summarize_typenames + hide_extra:
        for n in nodes:
            if n.typename() in environment_definitions.summarize_typenames:
                # node_names[n] = reform_msg('%s=' % str(n.id) + n.describe_set(params=['compact']).text)
                node_names[n] = reform_msg('%s=' % str(n.id) +
                                           ' / '.join(split_len(n.describe_set(params=['compact']).text, 25)))
    f = Digraph('Graph', filename='tmp/graph.gv') if f is None else f
    dir = 'BT' if environment_definitions.draw_vert else 'LR'
    f.attr(rankdir=dir, size='8,5', ranksep="0.02")
    f.attr('node', shape='rectangle')
    exc = [e for e in ex if parse_node_exception(e)[1] in nodes] if ex else []
    # mesg = [(n, m) for (n, m) in msg if n in nodes] if msg else []
    mesg = [m for m in msg if m.node in nodes] if msg else []

    if environment_definitions.show_nodes:
        do_draw_graph(f, node_names, goals, exc, mesg, id_off, subgraphs)
    if environment_definitions.show_dialog_id and id != 0:
        f.attr('node', shape='rectangle', style='', color='white', fontsize='', fontcolor='green', fillcolor='')
        f.node('Dialog #%d' % id)
    lnm = '##' + str(len(goals) + id_off)
    if environment_definitions.show_last_ok and environment_definitions.show_goal_id:
        nm = 'Success' if ok else 'Exception'
        col = 'green' if ok else 'red'
        f.attr('node', shape='rectangle', style='filled', color=col, fontsize='20', fontcolor='', fillcolor='')
        f.node('%s' % nm)
        f.attr('edge', color=saturate('#dddd00'), style='', arrowhead='none', fontsize='', fontcolor='', fillcolor='')
        f.edge(lnm, nm)
        lnm = nm
    if simp and environment_definitions.show_simp and environment_definitions.show_goal_id:
        f.attr('node', shape='rectangle', style='', color='red', fontsize='20', fontcolor='blue', fillcolor='',
               fontname='courier')
        f.node('##simp', label=split_sexp(fix_chars(simp)))
        f.attr('edge', color='white', style='', arrowhead='none', fontsize='', fontcolor='', fillcolor='')
        if environment_definitions.show_nodes:
            f.edge(lnm, '##simp')
        lnm = '##simp'
    if sexp and environment_definitions.show_sexp and environment_definitions.show_goal_id:
        f.attr('node', shape='rectangle', style='', color='black', fontsize='20', fontcolor='blue', fillcolor='',
               fontname='courier')
        if isinstance(sexp, list):
            sexp = '//'.join(sexp)
        f.node('sexp', label=split_sexp(fix_chars(sexp)))
        f.attr('edge', color='white', style='', arrowhead='none', fontsize='', fontcolor='', fillcolor='')
        if environment_definitions.show_nodes:
            f.edge(lnm, 'sexp')
        lnm = 'sexp'
    if txt and environment_definitions.show_txt and environment_definitions.show_goal_id:
        f.attr('node', shape='rectangle', style='', color='white', fontsize='35', fontcolor='', fillcolor='',
               fontname='italic')
        f.node('##txt', label=gen_split_NL(txt))
        f.attr('edge', color='white', style='', arrowhead='none', fontsize='', fontcolor='', fillcolor='')
        f.edge(lnm, '##txt')

    f.view()


def draw_all_graphs(d_context, id=0, ok=True, sexp=None, txt=None, simp=None):
    gls = d_context.goals + d_context.other_goals if environment_definitions.show_other_goals else d_context.goals
    draw_graphs(gls, d_context.exceptions, d_context.messages, id, ok, sexp, txt, simp)
