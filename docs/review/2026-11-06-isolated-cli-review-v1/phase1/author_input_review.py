import json, hashlib
from datetime import datetime, timezone, timedelta
from collections import Counter
from pathlib import Path

packet_path=Path('input_packet.json')
packet_bytes=packet_path.read_bytes()
packet=json.loads(packet_bytes)['items']
review=json.loads(Path('input_review_template.json').read_text())
review['reviewer_id']='CLI20261106R01'
byid={x['item_id']:x for x in packet}
# Each entry below is a manually authored semantic judgment. Citation positions
# are located mechanically only after selecting the relevant quotation.
judgments={}
def add(n,target,label,answer,citations,missing,ambiguity):
    judgments[f'Q{n:03d}']=(target,label,answer,citations,missing,ambiguity)

add(1,'Identify the recording artist of the 1962 hit record Sheila.','insufficient',None,
 [(1,'Sheila was a hit record in 1962.'),(5,'There was a 1962 hit recording of Sheila.')],
 'All five documents were checked. Documents 1 and 5 identify the title and year, but neither assigns the recording to an artist. The quiz, Squeeze profile, and Riley biography do not supply that artist-title relation.',
 'The title and year clearly select a recording; the uncertainty is its unnamed performer, not an identified competing recording.')
add(2,'Identify the city serving as the state capital of Ohio.','insufficient',None,
 [(3,'Columbus is a city in Ohio.'),(5,"Ohio's state government meets at the Statehouse.")],
 'All five documents were checked. Columbus is called a city and the largest city, and a Statehouse is mentioned, but its location and the state-capital relation are absent. The presidential biographies do not connect Columbus to that role.',
 'Largest city and state capital are different relations. No conflicting capital is supplied, and the capital cannot be selected from population information alone.')
add(3,"Identify the calendar year of the market debut of Wham-O's modern Hula Hoop.",'insufficient',None,
 [(1,'Wham-O introduced its modern Hula Hoop to the market.'),(2,"Commercial use of Wham-O's Hula Hoop began.")],
 'All five slots were checked, including the duplicate song text in slots 4 and 5. The market introduction and commercial use are asserted without a year. Dates in the Australian constitution and song excerpts concern other entities.',
 'Market debut has a clear target here. No date is supplied for that event; unrelated years cannot fill the gap.')
add(4,'Identify the access-code field value for fictional Unit U-215, using only these archive records.','insufficient',None,
 [(1,'Unit U-215 has a ledger entry. Unit U-757 has a ledger entry.'),(2,'The inspection code assigned to Unit U-757 is K-23434.'),(3,'Access code and inspection code are independent fields in this fictional archive.')],
 'All five documents were checked. U-215 has an entry, but no access-code value is given for it. K-23434 is an inspection code for U-757, differing in both field and unit. Independent fields and shareable values provide no rule transferring the value to U-215.',
 'The unit and requested field are explicit. Sharing of values is permitted, so equality is possible but is not established; there is no contradiction to resolve.')
add(5,'Identify the usual name of the battle Napoleon called Mont Saint Jean.','answerable','The Battle of Waterloo.',
 [(1,'Waterloo is the usual name of the battle that Napoleon and the French called Mont Saint-Jean.'),(3,'Mont Saint-Jean and Waterloo are two names for the same military encounter')],
 'No missing link is identified: documents 1 and 3 explicitly equate the requested battle name with Waterloo.',
 'Spacing and hyphenation of Mont Saint Jean do not change the referent. The recipe and other unrelated documents supply no competing identification.')
add(6,'Name the Japanese raw-fish dish described as bite-sized pieces with dipping sauces, vegetables, and wasabi.','insufficient',None,
 [(3,'The Japanese preparation uses sliced raw fish served with dipping sauce, vegetables and wasabi.'),(5,'Fresh raw-fish slices are accompanied by sauce and garnishes.')],
 'All five documents were checked. The relevant preparation and accompaniments are described, but the preparation is not named. The Nigerian snacks, chop suey definitions, and pescetarian discussion do not supply its Japanese dish-name relation.',
 'Slices versus bite-sized pieces is a minor descriptive difference; the decisive gap is an absent name, not an explicit competing dish identification.')
add(7,'Give the resulting quality or condition expressed by ameliorating something initially bad.','insufficient',None,
 [(2,'The verb ameliorate is used for a situation that is bad.'),(3,'Ameliorate concerns conditions that start out bad.')],
 'All five documents were checked. The two relevant statements specify only the starting condition, not the resulting change. The supplied word-book excerpt does not define ameliorate; the song review and golf do-over account do not establish its meaning.',
 'The question asks what the bad condition becomes, rather than whether the verb applies to bad conditions. No definition of that outcome is provided.')
add(8,'Identify the city serving as the state capital of Ohio.','insufficient',None,
 [(3,"Among Ohio's cities is Columbus."),(5,'The Ohio state government meets in the Statehouse.')],
 'All five documents were checked. City membership and largest-city claims identify Columbus as relevant, but do not make it the capital. The Statehouse is not geographically located, and neither presidential biography supplies the missing relation.',
 'There is no competing capital assertion. The distinction between being an Ohio city and being its capital prevents a complete answer.')
add(9,'Identify the shared specific entertainment form of Sorry! and Barbarossa.','insufficient',None,
 [(2,'Sorry! is based on Pachisi.'),(4,'Barbarossa is a plasticine-shaping German-style board game.')],
 'All five documents were checked. Barbarossa is explicitly a board game; Sorry! is only related to Pachisi, whose type is not given. That ancestry alone does not establish the shared board-game form without external knowledge. The dog, plant, and filmmaker texts do not fill it.',
 'The question seeks a common form, not necessarily the narrower German-style subtype. Board games is plausible, but Sorry! is not typed by the supplied text.')
add(10,"Identify the calendar year of the market debut of Wham-O's modern Hula Hoop.",'answerable','1958.',
 [(1,"The market debut of Wham-O's modern Hula Hoop took place in 1958."),(2,"1958 was the year in which commercial use of Wham-O's Hula Hoop began.")],
 'No missing link is identified: document 1 directly dates the market debut, and document 2 corroborates the year for commercial use.',
 'The modern Wham-O product and market-debut event are explicit; unrelated constitution and song dates do not compete with this date.')
add(11,'Identify the chief or principal river of Burma (Myanmar).','insufficient',None,
 [(1,'Myanmar, formerly Burma, has a river called the Irrawaddy.'),(4,'Irrawaddy and Ayeyarwady are names of that river.')],
 'All five documents were checked. The texts establish a river in Myanmar and its alternative names, but never its chief or principal status. The Laos map, Canadian river account, and Myanmar political story add no ranking of Burmese rivers.',
 'The Irrawaddy Magazine mentioned in the political article is not itself evidence about river rank. A river-name candidate is available, but the requested chief relation is missing.')
add(12,'Name the Japanese dish of raw-fish pieces served with dipping sauce, vegetables, and wasabi.','insufficient',None,
 [(3,'The Japanese preparation described here uses raw fish in slices with sauce, vegetables and wasabi.'),(5,'Fresh raw-fish slices are served with condiments and garnishes.')],
 'All five documents were checked. Documents 3 and 5 describe the target preparation without giving its name. The other three documents concern Nigerian snacks, chop suey, and a seafood-inclusive diet, and supply no name for that Japanese preparation.',
 'Condiments and garnishes are compatible with the question, but compatibility of ingredients does not supply an unnamed dish label.')
add(13,'Name the Japanese raw-fish preparation with sauce, vegetables, and wasabi.','answerable','Sashimi.',
 [(3,'Sashimi names the Japanese preparation described here: raw fish in slices with sauce, vegetables and wasabi.'),(5,'Fresh raw-fish slices with condiments and garnishes are served as sashimi.')],
 'No missing link is identified: the preparation described in the question is explicitly named sashimi in document 3 and reinforced by document 5.',
 'Slices and bite-sized pieces are compatible descriptions in this question. The unrelated cooked dishes do not contradict the direct identification.')
add(14,"Report the total number of RuPaul's Drag Race seasons recorded by the supplied series overview, not a current external total.",'answerable','Ten seasons.',
 [(3,"Ten is the season total shown in the provided RuPaul's Drag Race series overview."),(4,"In that overview, RuPaul's Drag Race has a recorded total of ten seasons.")],
 'No missing link is identified: both relevant overview statements directly give a total of ten.',
 'The question is restricted to this overview. Individual season numbers, contestant counts, and the All Stars excerpt are different quantities and do not conflict with that total.')
add(15,'Identify the usual name of the military encounter Napoleon called Mont Saint Jean.','insufficient',None,
 [(1,'The name Napoleon and the French used for the encounter was Mont Saint-Jean.'),(3,'The battlefield of that encounter lay along the Mont Saint-Jean ridge.')],
 'All five documents were checked. The French name and ridge location are supplied, but no alternative usual battle name is linked to that encounter. The Napoleon recipe account concerns Marengo and does not equate it with this battle; the saint and racing texts add no identification.',
 'A ridge location does not independently determine the requested alternate name. No text asserts competing alternate names.')
add(16,'Locate both Luoding and Dingzhou, allowing the country-level common location and the supplied provincial details.','answerable','Both are in China: Luoding is in western Guangdong, and Dingzhou is in Hebei Province in northern China.',
 [(1,'Luoding is a county-level city in western Guangdong, China.'),(5,'Dingzhou is a city in Hebei Province in northern China.')],
 'No missing link is identified: each named city has an explicit location, and both are explicitly placed in China.',
 'The question does not specify geographic granularity; giving the shared country and each supplied province resolves that harmless scope variation.')
add(17,"Report the season total in the supplied RuPaul's Drag Race series overview.",'answerable','Ten seasons.',
 [(3,"The supplied overview of RuPaul's Drag Race lists ten seasons."),(4,"The total number of seasons recorded in this RuPaul's Drag Race overview is ten.")],
 'No missing link is identified: documents 3 and 4 both explicitly state the requested overview total.',
 'The target is the overview total rather than the count of excerpts or a present-day season total. Season-specific and All Stars information addresses different scopes.')
add(18,'Give the episode count for Pretty Little Liars season 2.','insufficient',None,
 [(3,"Pretty Little Liars' second season is described in the supplied account."),(5,'That season originally ran from June 2011 through March 2012.')],
 'All five documents were checked. Season 2 is named and dated but has no episode total. The 22 episodes refer to Pretty Little Liars season 1, 20 to season 7, and 26 to My Little Pony season 8; none supplies the requested season-2 count.',
 'The pronoun in document 5 can reasonably refer to the season-2 account, but even that reading supplies only release dates, not an episode count.')
add(19,"Report the total seasons listed by the supplied RuPaul's Drag Race overview.",'insufficient',None,
 [(3,"The supplied overview describes the series RuPaul's Drag Race."),(4,"That RuPaul's Drag Race overview records information about the show's seasons.")],
 'All five documents were checked. Documents 3 and 4 refer to an overview without stating its total. The season-4 and season-2 excerpts show particular seasons, not the total; the All Stars season-1 excerpt is a separate titled series and cannot supply the main-series total.',
 'The wording asks for an overview total, not how many season snippets happen to be included. Neither the highest season number nor the number of documents determines that total.')
add(20,'Identify who recorded the 1962 hit Sheila.','insufficient',None,
 [(1,'A 1962 hit record was called Sheila.'),(5,'Sheila had a hit recording in 1962.')],
 'All five documents were checked. The title and date are repeated without a performer. The quiz names performers of other songs, the Squeeze article concerns another band, and the Riley biography identifies other hits; none attributes Sheila to an artist.',
 'The requested artist relation is clear, but matching the title and year alone does not identify an artist.')
add(21,'Identify the common type of games represented by Khet and Quarto.','answerable','Board games.',
 [(2,'Khet is a chess-like abstract strategy board game using lasers.'),(3,'Quarto is a board game for two players, invented by Blaise Müller.')],
 'No missing link is identified for the shared category board games: both named games are explicitly assigned that type.',
 'Khet is additionally called abstract strategy, but Quarto is not given that narrower label here. Board games is the supported shared level of classification.')
add(22,'State what a bad situation becomes when ameliorated.','answerable','Better, improved, or more tolerable.',
 [(2,'To ameliorate a bad situation is to make it better or improve it.'),(3,'When conditions are bad, ameliorate means that they have been made more tolerable.')],
 'No missing link is identified: both relevant statements define the resulting change from the initially bad condition.',
 'Better and more tolerable express compatible degrees of improvement; neither implies that all problems are completely eliminated.')
add(23,'Identify the cause of the urban-versus-surrounding-rural temperature difference.','answerable','Human modification of land surfaces is the main cause.',
 [(2,'The main cause of urban areas being warmer than surrounding rural areas is human modification of land surfaces.'),(4,'This urban heat island temperature difference is usually larger at night and most apparent when winds are weak.')],
 'No missing link is identified for the main cause: document 2 explicitly supplies the causal relation. Document 4 describes conditions under which the difference is larger or more apparent.',
 'The question can invite a mechanism or a phenomenon name. Its causal wording supports the stated main cause; the text calls the difference an urban heat island but does not claim surface modification is the sole cause.')
add(24,'Identify the common game type of Khet and Quarto.','insufficient',None,
 [(2,'Lasers and abstract strategy are involved in Khet, which is chess-like.'),(3,'Blaise Müller invented Quarto, which is played as a board game by two people.')],
 'All five documents were checked. Quarto is explicitly a board game. Khet is described by lasers, abstract strategy, and a chess comparison without an explicit board-game classification. The other board games are Hare and Tortoise and Backgammon, not Khet; the dog descriptions add no link.',
 'Board games is a plausible common category, but chess-like can describe rules or strategy without fixing physical form. Abstract strategy is only assigned to Khet, so that narrower shared type is also not established.')
add(25,'Give the number of episodes of Pretty Little Liars season 2.','insufficient',None,
 [(3,'The supplied account describes season two of Pretty Little Liars.'),(5,'The original release of that season ran from June 2011 to March 2012.')],
 'All five documents were checked. The relevant season is named and dated, but no total episodes are given for it. The explicit counts of 22, 26, and 20 belong respectively to PLL season 1, My Little Pony season 8, and PLL season 7.',
 'Release duration does not determine how many episodes aired. The surrounding season counts have clear different entity or season scopes.')
add(26,'Identify the access-code value assigned to fictional Unit U-352.','insufficient',None,
 [(1,'Unit U-352 has a ledger entry. Unit U-383 has a ledger entry.'),(2,'Access code and inspection code are independent fields in this fictional archive.'),(3,'The inspection code assigned to Unit U-352 is K-22280.')],
 'All five documents were checked. K-22280 is assigned to the target unit as its inspection code, not its access code. The archive explicitly makes those fields independent and gives no access-code assignment for U-352.',
 'The same value may occur across fields, so K-22280 is neither established nor ruled out as the access code. One value per field does not make different fields equal.')
add(27,'Identify the shared specific entertainment form of Sorry! and Barbarossa.','insufficient',None,
 [(2,'Pachisi is the basis for Sorry!.'),(4,'Plasticine shaping is used in Barbarossa, a German-style board game.')],
 'All five documents were checked. Barbarossa is typed as a board game, whereas Sorry! is only linked to an untyped Pachisi. Dog, plant, and filmmaker excerpts do not provide the missing common classification.',
 'A shared board-game category is plausible but requires knowing what Sorry! or Pachisi is beyond the supplied statements. The German-style and plasticine modifiers are only established for Barbarossa.')
add(28,'Give the total episode count for Pretty Little Liars season 2.','answerable','25 episodes.',
 [(3,'Season two of Pretty Little Liars contains 25 episodes.'),(5,'The episode total for Pretty Little Liars season two is 25')],
 'No missing link is identified: both relevant documents explicitly give 25 episodes for the requested show and season.',
 'Counts of 22 and 20 belong to other PLL seasons, and 26 belongs to a different show, so they do not conflict with the season-2 count.')
add(29,'Identify the artist who recorded the 1962 hit Sheila.','answerable','Tommy Roe.',
 [(1,'Tommy Roe recorded the 1962 hit Sheila.'),(5,'The 1962 hit recording of Sheila was by Tommy Roe.')],
 'No missing link is identified: documents 1 and 5 directly connect the artist to the requested title and year.',
 'Other artists in the quiz and biographies are attached to other songs and do not create a conflicting attribution of Sheila.')
add(30,'Identify the game category shared by Khet and Quarto.','answerable','Board games.',
 [(2,'Lasers are used in Khet, a chess-like board game in the abstract strategy tradition.'),(3,'Blaise Müller invented Quarto, which is played as a board game by two people.')],
 'No missing link is identified for the shared board-game category: it is explicitly given for both Khet and Quarto.',
 'The abstract-strategy modifier is supplied for Khet only. The answer is limited to the common board-game form, without extending that modifier to Quarto.')
add(31,'Locate both Luoding and Dingzhou geographically.','insufficient',None,
 [(1,'Luoding is a county-level city.'),(5,'Dingzhou is a city in Hebei Province in northern China.')],
 'All five documents were checked. Dingzhou is explicitly located, but Luoding has only administrative status, with no country or province. University, company, and lake locations concern other entities and cannot locate Luoding.',
 'The question permits either a shared country or separate provincial locations, but both readings need a geographic link for Luoding. A county-level designation alone does not provide that country.')
add(32,'Identify the chief river of Burma, also called Myanmar.','answerable','The Irrawaddy River, also called Ayeyarwady.',
 [(1,'The Irrawaddy River is the principal river of Myanmar, formerly Burma.'),(4,"The river known as the Irrawaddy or Ayeyarwady is Burma's chief river.")],
 'No missing link is identified: principal and chief status are expressly assigned to the named river in the target country.',
 'Principal and chief are compatible here, and the two river names are expressly equated. The magazine with a similar name is a different entity.')
add(33,'Identify why urban areas are warmer than their surrounding rural areas.','insufficient',None,
 [(2,'Urban areas are warmer than surrounding rural areas.'),(4,'This urban heat island temperature difference is usually larger at night and most apparent when winds are weak.')],
 'All five slots were checked. Document 2 restates the difference and document 4 describes timing and weak-wind visibility, but neither explains its underlying cause. The water-content definition and duplicate anthropomorphism excerpts give no causal connection to urban warming.',
 'Weak winds are described as making the contrast apparent, not as the general cause of cities being warmer. Naming urban heat island also names the phenomenon rather than supplying a mechanism.')
add(34,'State the resulting condition expressed by ameliorate when the original situation is bad.','answerable','Better or more tolerable.',
 [(2,'A bad situation becomes better when it is ameliorated.'),(3,'More tolerable conditions are what the verb ameliorate describes when the initial situation is bad.')],
 'No missing link is identified: the improvement from bad to better or more tolerable is directly stated.',
 'The two outcome descriptions are compatible and do not promise perfection or complete removal of the initial problem.')
add(35,'Explain the cause of the urban-rural temperature difference in which cities are warmer.','insufficient',None,
 [(2,'An urban area is warmer than the rural area around it.'),(4,"Weak winds make the urban heat island's urban-rural temperature contrast most apparent, and it is usually larger at night.")],
 'All five slots were checked. The relevant texts provide a temperature comparison and when it is prominent, but no underlying cause of the urban warmth. Water content is defined without an urban-temperature connection, and the duplicated anthropomorphism text is unrelated.',
 'A condition affecting apparent contrast is not automatically the cause of the temperature difference. The supplied text does not justify treating nighttime or weak winds as the requested primary mechanism.')
add(36,'Identify the state capital city of Ohio.','answerable','Columbus.',
 [(3,'Columbus is the state capital of Ohio.'),(5,"Ohio's state government meets at the Statehouse in Columbus, its capital city.")],
 'No missing link is identified: document 3 states the capital relation directly, and document 5 corroborates it with the Statehouse location.',
 'Largest-city information elsewhere is a separate property, compatible with the direct capital statements and unnecessary to infer them.')
add(37,'Identify the shared type of games Khet and Quarto.','insufficient',None,
 [(2,'Khet is chess-like, uses lasers, and involves abstract strategy.'),(3,'Quarto is a board game for two players, invented by Blaise Müller.')],
 'All five documents were checked. Quarto is explicitly a board game; Khet has a chess comparison and strategy features without that form being stated. Hare and Tortoise and Backgammon are separately typed games, and their category cannot be transferred to Khet merely because they share a packet.',
 'Chess-like supports a plausible board-game guess but can refer to strategic resemblance. The narrower abstract-strategy category is stated for Khet only, leaving no fully established shared specific type.')
add(38,'Identify the common entertainment form of Sorry! and Barbarossa.','answerable','Board games.',
 [(2,'Pachisi is the basis for the board game Sorry!.'),(4,'Plasticine shaping is used in Barbarossa, a German-style board game.')],
 'No missing link is identified: each named entertainment is explicitly classified as a board game.',
 'German-style and plasticine-shaping qualify Barbarossa only. The shared board-game form answers the question without assigning those narrower features to Sorry!.')
add(39,'Name the Japanese dish of raw-fish pieces served with dipping sauce, vegetables, and wasabi.','answerable','Sashimi.',
 [(3,'The Japanese dish of sliced raw fish served with dipping sauce, vegetables and wasabi is sashimi.'),(5,'Sashimi consists of fresh raw-fish slices accompanied by sauce and garnishes.')],
 'No missing link is identified: document 3 directly names the described dish, with compatible ingredient support in document 5.',
 'The question describes bite-sized pieces while the sources say slices; this does not create an alternative named preparation in these documents.')
add(40,'Identify the usual name of the encounter Napoleon called the Battle of Mont Saint Jean.','insufficient',None,
 [(1,'Napoleon and the French called the military clash the Battle of Mont Saint-Jean.'),(3,'That battle was fought along the Mont Saint-Jean ridge.')],
 'All five documents were checked. Documents 1 and 3 repeat the French name and location without naming an alternative. The Marengo discussion in the biography concerns its own battle and supplies no equivalence; the saint and racing documents add none.',
 'The referent is clear enough to ask for an alternate name, but the ridge wording does not provide it. There is no explicit inconsistent alternate identification.')
add(41,'Identify the shared specific form of entertainment of Sorry! and Barbarossa.','answerable','Board games.',
 [(2,'Sorry! is a board game based on Pachisi.'),(4,'Barbarossa is a plasticine-shaping German-style board game.')],
 'No missing link is identified: both named games have an explicit board-game classification.',
 'The supported common category is board games. The documents do not classify both as German-style or both as plasticine-shaping games.')
add(42,'Identify the chief river of Burma/Myanmar.','insufficient',None,
 [(1,'The Irrawaddy is a river of Myanmar, formerly Burma.'),(4,'That river is known as the Irrawaddy or Ayeyarwady.')],
 'All five documents were checked. Irrawaddy/Ayeyarwady is located in Myanmar and its names are linked, but no chief or principal designation is supplied. The Laos map, Canadian-river profile, and Myanmar politics article do not establish Burmese river rank.',
 'The magazine name in document 5 has no bearing on the requested river status. There is a relevant river candidate but no evidence selecting it as chief.')
add(43,'Identify the chief river of Burma, using the Myanmar country-name equivalence in the documents.','answerable','The Irrawaddy, also known as Ayeyarwady.',
 [(1,'Myanmar, formerly Burma, has the Irrawaddy as its principal river.'),(4,"Burma's chief river goes by the names Irrawaddy and Ayeyarwady.")],
 'No missing link is identified: documents 1 and 4 directly give the relevant status, country, and river names.',
 'Chief and principal describe the same requested role here; the explicit dual naming removes any uncertainty between Irrawaddy and Ayeyarwady.')
add(44,"Identify the year Wham-O's modern Hula Hoop entered the market.",'insufficient',None,
 [(1,"Wham-O's modern Hula Hoop made its market debut."),(2,"Wham-O's Hula Hoop entered commercial use.")],
 'All five slots were checked. The product debut and commercial use lack dates. Years in the constitution excerpt and duplicated song excerpt are attached to different historical events and do not date the Hula Hoop.',
 'The event and product are specific, but no year can be selected from their undated statements.')
add(45,'Identify the state capital of Ohio.','answerable','Columbus.',
 [(3,"Ohio's capital city is Columbus."),(5,"Columbus, Ohio's capital, is where the state government meets at the Statehouse.")],
 'No missing link is identified: the capital-city relation is explicit in documents 3 and 5.',
 'Other mentions of Columbus as the largest city do not change or compete with the separate capital relation.')
add(46,"Give the season total recorded by the supplied RuPaul's Drag Race series overview.",'insufficient',None,
 [(3,"RuPaul's Drag Race is the series described in the provided overview."),(4,"Information about that show's seasons is recorded in the overview.")],
 'All five documents were checked. The overview is named but its total is never stated. Season-2 and season-4 snippets establish individual main-series seasons, while All Stars season 1 is a separate scope; counting snippets or taking the largest displayed season number would not recover the overview total.',
 'The phrase how many seasons refers to the overview total, not the number of excerpted season entries. The supplied references to an overview cannot substitute for its unstated total.')
add(47,'Give the number of episodes in Pretty Little Liars season 2.','answerable','25 episodes.',
 [(3,"Pretty Little Liars' second season has a total of 25 episodes."),(5,'There are 25 episodes in season two, whose original broadcast ran from June 2011 through March 2012.')],
 'No missing link is identified: document 3 directly states the requested show-season count and document 5 reinforces that count and release scope.',
 'The unqualified season-two wording in document 5 reasonably continues the PLL account, and document 3 independently resolves its referent. Counts for other seasons or shows are not contradictions.')
add(48,"Identify the year of Wham-O's modern Hula Hoop market debut.",'answerable','1958.',
 [(1,'Wham-O introduced its modern Hula Hoop to the market in 1958.'),(2,"Commercial use of Wham-O's Hula Hoop began in 1958.")],
 'No missing link is identified: the modern product market introduction is explicitly dated, and the commercial-use statement agrees.',
 'The requested event is distinct from earlier hoop history or the unrelated dates in other excerpts. No competing debut year is supplied.')
add(49,'Give the resulting quality of a bad situation after it is ameliorated.','insufficient',None,
 [(2,'The word ameliorate is used about a bad situation.'),(3,'The verb ameliorate concerns conditions that are initially bad.')],
 'All five documents were checked. The relevant texts give the initial bad state, not the direction or result of change. The word-book excerpt ends without a definition of ameliorate; the song review and mulligan account do not define that verb.',
 'An initially bad condition alone does not indicate whether a verb makes it better, worse, or unchanged. The requested result remains unstated.')
add(50,'Locate both Luoding and Dingzhou, at least by country.','insufficient',None,
 [(1,'Luoding has the administrative status of a county-level city.'),(5,"In northern China's Hebei province is the city of Dingzhou.")],
 'All five documents were checked. Dingzhou is placed in Hebei, China, but Luoding receives an administrative classification with no geographic location. Locations of the universities, companies, and lakes do not locate Luoding.',
 'Either a shared country or two separate locations would answer the broad wording, but neither can be completed without a country or province relation for Luoding.')
add(51,'Identify the cause of urban areas being warmer than the surrounding rural areas.','answerable','Human changes to land surfaces are the chief explanation.',
 [(2,'Human changes to land surfaces chiefly explain why an urban area is warmer than the rural area around it.'),(4,"Weak winds make the urban heat island's urban-rural temperature contrast most apparent, and it is usually larger at night.")],
 'No missing link is identified for the main explanation: document 2 directly supplies it. The wind and nighttime statement concerns the contrast being apparent or larger, not an alternative exclusive cause.',
 'The causal question is answered at the level supplied by the text; no detailed physical mechanism or claim that this is the only contributing factor is supported or required.')
add(52,'Identify the access-code field for fictional Unit U-215 only.','insufficient',None,
 [(1,'Unit U-215 has a ledger entry. Unit U-757 has a ledger entry.'),(2,'The access code assigned to Unit U-757 is K-81486.'),(3,'Each unit has one value per field; values can be shared across units and fields.')],
 'All five documents were checked. An access code is supplied for U-757, but none is assigned to U-215. Shared values are allowed, not mandated, so K-81486 cannot be transferred from the other unit without a linking rule.',
 'The requested field matches document 2 but the unit does not. The records neither prove nor exclude equality of the two access codes; this is missing evidence, not a conflict.')
add(53,'Locate Luoding and Dingzhou, including their common country and any supplied regional detail.','answerable','Both are in China: Luoding is in western Guangdong, and Dingzhou is in Hebei province in northern China.',
 [(1,'China contains Luoding, a county-level city in western Guangdong.'),(5,"In northern China's Hebei province is the city of Dingzhou.")],
 'No missing link is identified: the country and regional locations of both cities are expressly supplied.',
 'The broad where wording permits country-level or provincial detail; the answer provides both without assuming that the cities share a province.')
add(54,'Identify who recorded the 1962 hit Sheila.','answerable','Tommy Roe.',
 [(1,"The artist behind Sheila's 1962 hit recording was Tommy Roe."),(5,'Sheila was recorded as a 1962 hit by Tommy Roe.')],
 'No missing link is identified: both relevant documents directly attribute the recording and its year to Tommy Roe.',
 'The possessive phrasing in document 1 denotes the title recording, and document 5 makes the artist relation explicit. Other songs and artists in the packet do not compete with this attribution.')
add(55,'Identify the usual battle name corresponding to Napoleon and the French name Mont Saint Jean.','answerable','The Battle of Waterloo.',
 [(1,'The military clash called the Battle of Mont Saint-Jean by Napoleon and the French is known as the Battle of Waterloo.'),(3,'The Battle of Waterloo was fought along the Mont Saint-Jean ridge; Mont Saint-Jean was the French name for that battle.')],
 'No missing link is identified: document 1 explicitly equates the two battle names, and document 3 independently connects them and the ridge.',
 'The ridge and battle-name uses of Mont Saint-Jean are distinguished in the text. Both relevant statements identify the same encounter and give no incompatible alternate name.')

assert len(judgments)==55
for item in review['items']:
    key=item['item_id']
    target,label,answer,selections,missing,ambiguity=judgments[key]
    support=[]
    for di,quote in selections:
        doc=byid[key]['documents'][di-1]
        start=doc.index(quote)
        support.append({'document_index':di,'start':start,'end':start+len(quote),'quote':quote})
    item.update(status='reviewed',target_interpretation=target,answerability=label,candidate_answer=answer,document_support=support,missing_link=missing,ambiguity=ambiguity,conflicting_propositions=[])

completed=datetime.now(timezone(timedelta(hours=8))).isoformat()
review['completed_at']=completed
Path('input_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
review_hash=hashlib.sha256(Path('input_review.json').read_bytes()).hexdigest()
context=json.loads(Path('reviewer_context_template.json').read_text())
context.update(reviewer_id='CLI20261106R01',reviewed_at=completed,
 prior_project_history_exposure=False,prior_author_ratings_exposure=False,
 prior_outputs_or_probe_results_exposure=False,coordinator_material_exposure=False,
 instructions_or_hidden_context_exposure=False,
 exposure_description='Before opening the input packet, the received context contained ordinary operating instructions, workspace/session metadata, the user context-audit request, and this reviewer\'s audit response. No specific research project history, prior author judgments or label counts, model answer or probe-result summaries, coordinator case mappings, or project-specific handoff contents were received or inspected. The phase1 task supplied stage instructions and reviewer ID; the blank templates and review instructions supplied procedure, not prior project judgments. The audit can_proceed=false meant only that separate instruction and input were awaited. During this stage only the named stage instructions, blank templates, input packet, and this review\'s generated files were read. No answer packet was viewed or requested.',
 input_first_process_actually_followed=True,
 actual_independence_determination='An input-first process was followed in this session, with no identified prior exposure in the five requested categories. This is a bounded self-report about received context and observed tool use, not proof of absolute independence, an assessment of uninspected files or other sessions, or automatic independent approval. A new session, anonymized item IDs, programmatic hashes, and coverage checks do not establish semantic independence. The resulting input judgments are complete before any answer review; coordinator sealing is a subsequent external step.')
context['input_review_sha256']=review_hash
context['input_review_completed_at']=completed
Path('context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2)+'\n')

inventory=json.loads(Path('reading_inventory.json').read_text())
unique={d['sha256']:d for d in inventory['unique_documents']}
slots=[]
for item in packet:
    slots.append({'item_id':item['item_id'],'question_sha256_utf8':hashlib.sha256(item['question'].encode()).hexdigest(),
      'question_read_declared':True,'all_five_documents_assessed_for_this_question_declared':True,
      'documents':[{'document_index':i,'read_id':unique[hashlib.sha256(d.encode()).hexdigest()]['read_id'],
       'sha256_utf8':hashlib.sha256(d.encode()).hexdigest(),'unicode_characters':len(d),'utf8_bytes':len(d.encode()),
       'full_text_read_declared':True,'reconnected_to_item_question_declared':True} for i,d in enumerate(item['documents'],1)]})
reading_log={
 'reviewer_id':'CLI20261106R01','completed_at':completed,
 'reading_declaration':{'all_55_questions_read':True,'all_275_document_slots_assessed':True,
 'method':'Exact UTF-8 text deduplication for reading only; all distinct texts displayed in full in bounded terminal outputs, then each of the 275 slots reconnected to its actual question. Q001 displayed documents 1-5; subsequent outputs displayed distinct read IDs 6-24, 25-36, 37-64, 65-105, and 106-140. No displayed content was truncated.',
 'semantic_review':'All 55 judgments were manually reasoned and authored individually. Code located selected quotations, calculated hashes, serialized judgments, and checked structure; it did not assign semantic labels.',
 'limits':'Reading and semantic assessment are reviewer declarations. Programmatic byte/hash coverage verifies identity and mapping, not comprehension or independent approval.'},
 'programmatically_verified_coverage':{'packet_items':len(packet),'document_slots':sum(len(x['documents']) for x in packet),
 'unique_document_texts':len(unique),'packet_sha256':hashlib.sha256(packet_bytes).hexdigest(),
 'every_document_slot_matches_inventory_text_and_hash':all(unique[hashlib.sha256(d.encode()).hexdigest()]['text']==d for it in packet for d in it['documents']),
 'unique_text_utf8_bytes':sum(len(d['text'].encode()) for d in unique.values()),
 'all_slot_utf8_bytes':sum(len(d.encode()) for it in packet for d in it['documents'])},
 'unique_documents':[{'read_id':d['read_id'],'sha256_utf8':d['sha256'],'unicode_characters':len(d['text']),
 'utf8_bytes':len(d['text'].encode()),'displayed_character_ranges':[[0,len(d['text'])]],'full_read_declared':True} for d in inventory['unique_documents']],
 'items':slots,'input_review_sha256':review_hash,'input_review_completed_at':completed}
Path('input_reading_log.json').write_text(json.dumps(reading_log,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'written':['input_review.json','context.json','input_reading_log.json'],'counts':dict(Counter(x['answerability'] for x in review['items'])),'input_review_sha256':review_hash,'completed_at':completed},indent=2))
