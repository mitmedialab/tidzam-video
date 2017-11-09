BlueHeron = ['little blue heron', 'American egret']
CanadianGoose = ['goose']
BlackGrouse = ['black groose']
BeeEater = ['bee eater']
WillowPtarmigan = ['ptarmigan']
Cuckoo = ['water ouzel']
Woodpecker = ['magpie']
Swift = ['kite']
Quail = ['quail']
Pheasant = ['cock']
Chicken = ['cock', 'hen']
Human = ['jersey', 'jean', 'miniskirt', 'sweatshirt', 'sunglass',
         'suit', 'bow tie', 'cloack', 'abay', 'diaper', 'cardigan', 
         'sock', 'cowboy boot', 'lab coat', 'medecine chest', 
         'swimming trunks', 'bikini', 'maillot', 'brassiere', 
         'running shoe', 'lipstick', 'face powder', 'loupe', 'mask', 
         'wool', 'lotion', 'band aid', 'knee pad', 'sock', 'sandal']

Labels = [{'label': 'Blue Heron', 'set': BlueHeron},
          {'label': 'Canadian Goose', 'set': CanadianGoose},
          {'label': 'Black Grouse', 'set': BlackGrouse},
          {'label': 'Bee Eater', 'set': BeeEater}, 
          {'label': 'Willow Ptarmigan', 'set': WillowPtarmigan}, 
          {'label': 'Cuckoo', 'set': Cuckoo}, 
          {'label': 'Woodpecker', 'set': Woodpecker}, 
          {'label': 'Swift', 'set': Swift}, 
          {'label': 'Quail', 'set': Quail}, 
          {'label': 'Pheasant', 'set': Pheasant}, 
          {'label': 'Chicken', 'set': Chicken}, 
          {'label': 'Human', 'set': Human}]

def validate_labels(top_k):
	top_k_valid = []
	for patch in top_k:
		labels = []
		for label in Labels:
			for pred in patch:
				if (not label['label'] in labels) and (pred.score > 15) and (pred.label in label['set']):
						labels.append(label['label'])
		top_k_valid.append(labels)
	return top_k_valid
