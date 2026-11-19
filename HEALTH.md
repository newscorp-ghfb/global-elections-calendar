# Elections calendar health

- Generated: 2026-11-19T00:13:03.957238Z
- Outcome: published
- Verdict: green
- Severity: warning
- Data as of: 2026-11-19T00:13:04.866749Z
- Feed: 390987 bytes of a 524288 byte budget

## Run

No run reasons.

## Sources

| Source | Severity | Acceptance | Served data fetched | Open reasons |
| --- | --- | --- | --- | --- |
| ElectionGuide | ok | promoted | 2026-11-19T00:13:05.079020Z | 0 |
| OSCE\/ODIHR | ok | promoted | 2026-11-19T00:13:06.579982Z | 0 |
| Wikipedia | warning | promoted | 2026-11-19T00:13:04.866749Z | 0 (+2 known) |
| NDI | warning | promoted | 2026-11-19T00:13:05.498848Z | 0 (+1 known) |
| A\-WEB | warning | promoted | 2026-11-19T00:13:06.378362Z | 0 (+2 known) |
| EISA | warning | promoted | 2026-11-19T00:13:09.096165Z | 0 (+1 known) |
| IPU | warning | promoted | 2026-11-19T00:13:07.042685Z | 0 (+1 known) |
| Carter Center | ok | promoted | 2026-11-19T00:13:07.500307Z | 0 |
| EEAS | ok | promoted | 2026-11-19T00:13:07.211145Z | 0 |

## ElectionGuide

- Download: ok; HTTP 200; 916364 bytes, 3 attempts, 1903 ms; pages 3 of 3 ok, 0 failed, stop complete; url https\:\/\/www\.electionguide\.org\/elections\/type\/upcoming\/
- Parse: parser 2\.0; 329 units (226 parsed, 0 partial, 2 unparsed, 101 ignored); 226 claims; relevance 0 in or after the window, 0 unknown, 2 before it; 262 ms
- Ignored: duplicate 101
- Coverage: all: 3 pages, 329 units, ok
- Snapshot: promoted; fallback no; served 9ab2661d87ebb5a1dd72ec41eafbdc50ced7e6b56d06e95efc4a861261328987, fetched 2026-11-19T00:13:05.079020Z; baseline units 329; comparable yes
- Match: 32 of 40 eligible matched, 8 unmatched, 8 fresh peers, informative yes

### Reasons

- **info** units\_disappeared: listed events no longer listed\: 1

### No longer listed

- No longer listed by ElectionGuide\: Fiji \| Referendum \| 2026\-12\-09 \(t\) \| 2026\-12\-09 \(t\) \| Date not confirmed \| No\, was 2026\-12\-09 \(t\) to 2026\-12\-09 \(t\)

## OSCE\/ODIHR

- Download: ok; HTTP 200; 754018 bytes, 1 attempts, 1914 ms; pages 1 of 1 ok, 0 failed, stop complete; url https\:\/\/odihr\.osce\.org\/odihr\/elections
- Parse: parser 2\.0; 634 units (173 parsed, 7 partial, 454 unparsed, 0 ignored); 180 claims; relevance 0 in or after the window, 0 unknown, 461 before it; 263 ms
- Ignored: none
- Coverage: all: 1 pages, 634 units, ok
- Snapshot: promoted; fallback no; served fa16c788371dfc4a6662714891936512ea9a69de6be99c5bbe544fbbaa590615, fetched 2026-11-19T00:13:06.579982Z; baseline units 634; comparable yes
- Match: 5 of 5 eligible matched, 0 unmatched, 5 fresh peers, informative yes

### Reasons

No reasons.

## Wikipedia

- Download: ok; HTTP 200; 581784 bytes, 4 attempts, 426 ms; pages 4 of 4 ok, 0 failed, stop complete; url https\:\/\/en\.wikipedia\.org\/w\/api\.php\?action\=parse\&page\=2026\_national\_electoral\_calendar\&prop\=text\%7Crevid\&format\=json\&formatversion\=2\&maxlag\=5
- Parse: parser 2\.0; 728 units (489 parsed, 64 partial, 53 unparsed, 122 ignored); 601 claims; relevance 81 in or after the window, 36 unknown, 0 before it; 323 ms
- Ignored: container\_item 122
- Coverage: 2026: 2 pages, 618 units, ok; 2027: 2 pages, 110 units, ok
- Snapshot: promoted; fallback no; served 34ad360b550f2851d6bba75c8eda8650408ed4322bd874dd9976060b115b3fc6, fetched 2026-11-19T00:13:04.866749Z; baseline units 727; comparable yes
- Match: 32 of 54 eligible matched, 22 unmatched, 8 fresh peers, informative yes

### Reasons

- **warning** unparsed\_relevant: relevant units unparsed\: 53 — known: all of these units were in the last served data, so the run is not red for it
- **warning** partial\_relevant: relevant units partly parsed\: 64 — known: all of these units were in the last served data, so the run is not red for it

### Unparsed samples

- 6 December Northern Cyprus\, Assembly of the Republic
- 3 April\: Myanmar\, Vice President
- January\: Indonesia\, Vice President
- April and October\: India\, Rajya Sabha
- 19 May\: United States \> Oregon \> Commissioner of Labor

## NDI

- Download: ok; HTTP 200; 342675 bytes, 2 attempts, 906 ms; pages 2 of 2 ok, 0 failed, stop complete; url https\:\/\/www\.ndi\.org\/elections\-calendar\?page\=0
- Parse: parser 2\.0; 34 units (33 parsed, 1 partial, 0 unparsed, 0 ignored); 34 claims; relevance 0 in or after the window, 1 unknown, 0 before it; 155 ms
- Ignored: none
- Coverage: all: 2 pages, 34 units, ok
- Snapshot: promoted; fallback no; served 9138facaa71fd8f9902127b24179f19a98ab22eea354a21110da9aba2db23bd8, fetched 2026-11-19T00:13:05.498848Z; baseline units 34; comparable yes
- Match: 3 of 5 eligible matched, 2 unmatched, 7 fresh peers, informative yes

### Reasons

- **warning** partial\_relevant: relevant units partly parsed\: 1 — known: all of these units were in the last served data, so the run is not red for it

## A\-WEB

- Download: ok; HTTP 200; 49405 bytes, 1 attempts, 999 ms; pages 1 of 1 ok, 0 failed, stop complete; url https\:\/\/www\.aweb\.org\/eng\/bbs\/B0000007\/list\.do\?menuNo\=300052\&option\=all
- Parse: parser 2\.0; 31 units (29 parsed, 1 partial, 1 unparsed, 0 ignored); 30 claims; relevance 0 in or after the window, 2 unknown, 0 before it; 19 ms
- Ignored: none
- Coverage: 2026: 1 pages, 31 units, ok
- Snapshot: promoted; fallback no; served 2ebc4d6e9a585607324e6cc3a2234a002a716dac33cb7ae00e9413f093431840, fetched 2026-11-19T00:13:06.378362Z; baseline units 31; comparable yes
- Match: 2 of 2 eligible matched, 0 unmatched, 7 fresh peers, informative no

### Reasons

- **warning** unparsed\_relevant: relevant units unparsed\: 1 — known: all of these units were in the last served data, so the run is not red for it
- **warning** partial\_relevant: relevant units partly parsed\: 1 — known: all of these units were in the last served data, so the run is not red for it

### Unparsed samples

- Ghana \| 2026 The Presidential Primaries \| 31 Jan 2026

## EISA

- Download: not\_published\_yet; HTTP 200; 532457 bytes, 2 attempts, 4037 ms; pages 2 of 2 ok, 0 failed, stop complete; url https\:\/\/www\.eisa\.org\/election\-calendar\/
- Parse: parser 2\.0; 22 units (20 parsed, 0 partial, 2 unparsed, 0 ignored); 25 claims; relevance 0 in or after the window, 2 unknown, 0 before it; 66 ms
- Ignored: none
- Coverage: 2026: 1 pages, 22 units, ok; all: 1 pages, 0 units, ok
- Snapshot: promoted; fallback no; served 4c3f95221e42e021ff808adbd10558e9a25add855550d43427b4337f4a3ba29d, fetched 2026-11-19T00:13:09.096165Z; baseline units 22; comparable yes
- Match: 2 of 4 eligible matched, 2 unmatched, 6 fresh peers, informative no

### Reasons

- **info** not\_published\_yet: no heading \'eisa african election calendar 2027\'
- **warning** unparsed\_relevant: relevant units unparsed\: 2 — known: all of these units were in the last served data, so the run is not red for it

### Unparsed samples

- Libya \| Presidential \| Postponed from April 2026
- Libya \(from the row above\) \| House of Representatives \| Postponed from April 2026

## IPU

- Download: ok; HTTP 200; 393071 bytes, 1 attempts, 373 ms; pages 1 of 1 ok, 0 failed, stop complete; url https\:\/\/data\.ipu\.org\/elections\/
- Parse: parser 2\.0; 281 units (234 parsed, 0 partial, 4 unparsed, 43 ignored); 234 claims; relevance 4 in or after the window, 0 unknown, 0 before it; 150 ms
- Ignored: appointed\_chamber 28, inactive\_chamber 10, no\_expected\_date 5
- Coverage: all: 1 pages, 281 units, ok
- Snapshot: promoted; fallback no; served d3c92db67143909676db63815e248d6052db6af7e29e543e44f114c46595df0a, fetched 2026-11-19T00:13:07.042685Z; baseline units 281; comparable yes
- Match: 7 of 10 eligible matched, 3 unmatched, 6 fresh peers, informative yes

### Reasons

- **warning** unparsed\_relevant: relevant units unparsed\: 4 — known: all of these units were in the last served data, so the run is not red for it

### Unparsed samples

- Benin \| Senate \| Bicameral \| Upper chamber \| Other \| 30 Jul 2026 \| 30 Jul 2026 \| 30 Jul 2031
- Burkina Faso \| People’s Legislative Assembly \| Unicameral \| Other \| 27 Mar 2026 \| 27 Mar 2026 \| 31 Jul 2029
- Lesotho \| Senate \| Bicameral \| Upper chamber \| Other \| 02 Nov 2022 \| 03 Nov 2022 \| 30 Nov 2027
- United Arab Emirates \| Federal National Council \| Unicameral \| Other \| 07 Oct 2023 \| 06 Nov 2023 \| 31 Oct 2027

## Carter Center

- Download: ok; HTTP 200; 154176 bytes, 1 attempts, 616 ms; pages 1 of 1 ok, 0 failed, stop complete; url https\:\/\/www\.cartercenter\.org\/programs\/democracy\/elections\-observed\/
- Parse: parser 2\.0; 61 units (14 parsed, 0 partial, 46 unparsed, 1 ignored); 18 claims; relevance 0 in or after the window, 0 unknown, 46 before it; 24 ms
- Ignored: footnote 1
- Coverage: all: 1 pages, 61 units, ok
- Snapshot: promoted; fallback no; served 5ef60e154de68ad8456509a4cdf002f221d86ee65a04438c90e88ee8aa24f02a, fetched 2026-11-19T00:13:07.500307Z; baseline units 61; comparable yes
- Match: 0 of 0 eligible matched, 0 unmatched, 0 fresh peers, informative no

### Reasons

No reasons.

## EEAS

- Download: ok; HTTP 200; 184404 bytes, 1 attempts, 287 ms; pages 1 of 1 ok, 0 failed, stop complete; url https\:\/\/www\.eeas\.europa\.eu\/eeas\/eu\-election\-observation\-missions\-1\_en
- Parse: parser 2\.0; 34 units (24 parsed, 0 partial, 0 unparsed, 10 ignored); 24 claims; relevance 0 in or after the window, 0 unknown, 0 before it; 33 ms
- Ignored: empty\_cell 6, year\_heading 4
- Coverage: all: 1 pages, 34 units, ok
- Snapshot: promoted; fallback no; served 9cf7f6a2113cc37c40efac39aaabee87128fb0fc1c3bf523034cf651184a807a, fetched 2026-11-19T00:13:07.211145Z; baseline units 34; comparable yes
- Match: 1 of 1 eligible matched, 0 unmatched, 6 fresh peers, informative no

### Reasons

No reasons.

## Attention items

| Kind | Source | Date | Text |
| --- | --- | --- | --- |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Michigan\, Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> District of Columbia\, Mayor and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Florida \> Governor\, Lieutenant Governor\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Illinois\, Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Minnesota \> Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Georgia\, Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Texas \> Governor\, Lieutenant Governor\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Rhode Island\, Governor\, Lieutenant Governor\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> South Carolina\, Governor\, Lieutenant Governor\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> New Mexico\, Governor\, Lieutenant Governor\, and Secretary of State |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Ohio\, Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Iowa\, Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> New York\, Governor\, Lieutenant Governor\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Oklahoma\, Governor\, Lieutenant Governor\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> California \> Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Wisconsin\, Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Arizona\, Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Massachusetts\, Governor\, Lieutenant Governor\, Secretary of the Commonwealth\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Maryland\, Governor\, Lieutenant Governor\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Vermont\, Governor\, Lieutenant Governor\, and ballot measure |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Alabama\, Governor\, Lieutenant Governor\, Secretary of State\, Attorney General\, ballot measures\, and local elections |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Arkansas\, Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Nevada \> Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> South Dakota\, Governor\, Lieutenant Governor\, Secretary of State\, Attorney General\, and ballot measure |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Colorado\, Governor\, Lieutenant Governor\, Secretary of State\, and Attorney General |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Connecticut\, Governor\, Lieutenant Governor\, Secretary of the State\, Attorney General\, Comptroller\, and Treasurer |
| partial\_unit | Wikipedia | 2026-11-03 | 3 November\: United States\, midterm elections \> Kansas\, Governor\, Lieutenant Governor\, Secretary of State\, Attorney General\, and ballot measure |
| partial\_unit | Wikipedia | 2026-11-15 | 15–16 November\: Italy\, Chieti\, by\-election |
| disappeared\_unit | ElectionGuide | 2026-12-09 | No longer listed by ElectionGuide\: Fiji \| Referendum \| 2026\-12\-09 \(t\) \| 2026\-12\-09 \(t\) \| Date not confirmed \| No\, was 2026\-12\-09 \(t\) to 2026\-12\-09 \(t\) |
| partial\_unit | Wikipedia | 2027-06-06 | 6 June\: \> Mexico\, state elections |
| partial\_unit | Wikipedia | 2027-10-01 | 5 October \> 2027 Manitoba general election |
| partial\_unit | Wikipedia | 2027-10-01 | 5 October \> 2027 Northwest Territories general election |
| partial\_unit | Wikipedia | 2027-11-02 | 2 November\: United States\, off\-year elections |
| unparsed\_unit | Wikipedia |  | 3 November\: United States\, midterm elections \> Minnesota \> Hennepin County\, County Attorney |
| unparsed\_unit | Wikipedia |  | 13 March\: 2027 New South Wales state election |
| undated\_listing | Wikipedia |  | Lesotho\: Parliament \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 18 April\: \> 2027 Schleswig\-Holstein state election |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish local elections \> 2027 Zaragoza municipal election |
| undated\_listing | NDI |  | Haiti\: 2026 Haiti General Election \(Phase 1\) \(Date TBD\) \(2026\)\, date not given |
| undated\_listing | Wikipedia |  | Cameroon\: Parliament \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 17 March\: 2027 Dutch provincial elections |
| undated\_listing | OSCE\/ODIHR |  | Poland\: Parliamentary Elections \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 2027 Goa Legislative Assembly election |
| unparsed\_unit | Wikipedia |  | 2027 Tyrolean state election |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Madrilenian regional election |
| undated\_listing | Wikipedia |  | Papua New Guinea\: Parliament \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections |
| unparsed\_unit | IPU |  | United Arab Emirates \| Federal National Council \| Unicameral \| Other \| 07 Oct 2023 \| 06 Nov 2023 \| 31 Oct 2027 |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Riojan regional election |
| unparsed\_unit | Wikipedia |  | 7 May\: 2027 United Kingdom local elections \> 2027 Northern Ireland Assembly election |
| unresolved\_evidence | EEAS |  | Peru\: EU election observation mission \(2026\) |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish local elections |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Valencian regional election |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Asturian regional election |
| unparsed\_unit | Wikipedia |  | 3 November\: United States\, midterm elections \> Indiana\, Secretary of State |
| undated\_listing | Wikipedia |  | Italy\: Chamber of Deputies \(2027\)\, date not given |
| unparsed\_unit | IPU |  | Lesotho \| Senate \| Bicameral \| Upper chamber \| Other \| 02 Nov 2022 \| 03 Nov 2022 \| 30 Nov 2027 |
| undated\_listing | Wikipedia |  | India\: Municipal Corporation \(2026\)\, date not given |
| undated\_listing | Wikipedia |  | Libya\: President \(2027\)\, date not given |
| undated\_listing | Wikipedia |  | Equatorial Guinea\: Parliament \(2027\)\, date not given |
| undated\_listing | Wikipedia |  | Bahrain\: Parliament \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 7 May\: 2027 United Kingdom local elections \> 2027 Welsh local elections |
| undated\_listing | Wikipedia |  | Poland\: Sejm \(2027\)\, date not given |
| undated\_listing | Wikipedia |  | Dominica\: Parliament \(2027\)\, date not given |
| undated\_listing | Wikipedia |  | Saint Kitts and Nevis\: Parliament \(2027\)\, date not given |
| undated\_listing | Wikipedia |  | Tunisia\: Parliament \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 2027 Uttarakhand Legislative Assembly election |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Canarian regional election |
| undated\_listing | OSCE\/ODIHR |  | Montenegro\: Parliamentary Elections \(2027\)\, date not given |
| undated\_listing | OSCE\/ODIHR |  | Greece\: Parliamentary Elections \(2027\)\, date not given |
| unresolved\_evidence | EEAS |  | Sao Tome and Principe\: EU election observation mission \(2026\) |
| undated\_listing | Wikipedia |  | Republic of the Congo\: Parliament \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 7 May\: 2027 United Kingdom local elections \> 2027 Scottish local elections |
| undated\_listing | EISA |  | Western Sahara\: Sahrawi legislative election \(2026\)\, date not given |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish local elections \> 2027 Valencia municipal election |
| undated\_listing | OSCE\/ODIHR |  | Tajikistan\: Presidential Election \(2027\)\, date not given |
| undated\_listing | Wikipedia |  | United Arab Emirates\: Parliament \(2027\)\, date not given |
| undated\_listing | EISA |  | Somaliland\: House of Elders \(Guitr\) \(2028\)\, date not given |
| undated\_listing | Wikipedia |  | Italy\: Senate \(2027\)\, date not given |
| undated\_listing | EISA |  | Somaliland\: House of Representatives \(2028\)\, date not given |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish local elections \> 2027 Madrid municipal election |
| unparsed\_unit | Wikipedia |  | 26 September\: 2027 Lower Saxony state election |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Murcian regional election |
| unparsed\_unit | Wikipedia |  | 6 December Northern Cyprus\, Assembly of the Republic |
| unparsed\_unit | Wikipedia |  | 7 May\: 2027 United Kingdom local elections \> 2027 Northern Ireland local elections |
| unparsed\_unit | Wikipedia |  | 2027 Manipur Legislative Assembly election |
| undated\_listing | OSCE\/ODIHR |  | Slovenia\: Presidential Election \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 2027 Prince Edward Island general election |
| unparsed\_unit | Wikipedia |  | 2027 Uttar Pradesh Legislative Assembly election |
| unparsed\_unit | Wikipedia |  | 2027 Sicilian regional election |
| unparsed\_unit | Wikipedia |  | 2027 Italian local elections |
| unparsed\_unit | Wikipedia |  | 30 May\: 2027 Bremen state election |
| unparsed\_unit | Wikipedia |  | 2027 Argentine provincial elections |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Balearic regional election |
| unparsed\_unit | IPU |  | Burkina Faso \| People’s Legislative Assembly \| Unicameral \| Other \| 27 Mar 2026 \| 27 Mar 2026 \| 31 Jul 2029 |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Navarrese regional election |
| unresolved\_evidence | EEAS |  | Zambia\: EU election observation mission \(2026\) |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Cantabrian regional election |
| undated\_listing | OSCE\/ODIHR |  | Italy\: Parliamentary Elections \(2027\)\, date not given |
| unresolved\_evidence | EEAS |  | Bangladesh\: EU election observation mission \(2026\) |
| undated\_listing | Wikipedia |  | Madagascar\: President \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 2027 Gujarat Legislative Assembly election |
| unparsed\_unit | Wikipedia |  | 17 October\: 2027 Ålandic legislative election |
| unparsed\_unit | Wikipedia |  | 2027 Himachal Pradesh Legislative Assembly election |
| unparsed\_unit | Wikipedia |  | 25 April\: 2027 North Rhine\-Westphalia state election |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish regional elections \> 2027 Castilian\-Manchegan regional election |
| undated\_listing | Wikipedia |  | Poland\: Senate \(2027\)\, date not given |
| unparsed\_unit | Wikipedia |  | 2027 Alberta general election |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish local elections \> 2027 Barcelona municipal election |
| unparsed\_unit | Wikipedia |  | 7 May\: 2027 United Kingdom local elections |
| unparsed\_unit | Wikipedia |  | 2027 Punjab Legislative Assembly election |
| unparsed\_unit | Wikipedia |  | 23 May\: \> 2027 Spanish local elections \> 2027 Seville municipal election |
| unresolved\_evidence | EEAS |  | Colombia\: EU election observation mission \(2026\) |
| unparsed\_unit | Wikipedia |  | 2027 Upper Austrian state election |
| unparsed\_unit | IPU |  | Benin \| Senate \| Bicameral \| Upper chamber \| Other \| 30 Jul 2026 \| 30 Jul 2026 \| 30 Jul 2031 |
| unparsed\_unit | Wikipedia |  | 7 March\: 2027 Lithuanian municipal elections |
| unparsed\_unit | Wikipedia |  | 18 April\: \> 2027 Saarland state election |
| undated\_listing | Wikipedia |  | Libya\: Parliament \(2027\)\, date not given |
| undated\_listing | OSCE\/ODIHR |  | Bulgaria\: Local Elections \(2027\)\, date not given |
| partial\_unit | A\-WEB | 2026-01-24 | Pakistan \| 2026 Gilgit Baltistan Assembly Election \| 24 Jan 2026 |
| partial\_unit | Wikipedia | 2026-02-23 | 23 February\: Canada\, Quebec\, Chicoutimi\, by\-election |
| partial\_unit | Wikipedia | 2026-03-03 | 3–8 March\: Iran\, Supreme Leader |
| partial\_unit | Wikipedia | 2026-03-07 | 7 March\: Australia\, Northern Territory\, Nightcliff by\-election |
| partial\_unit | Wikipedia | 2026-03-08 | 8 March\: \> Switzerland \> Nidwalden\, Landrat |
| partial\_unit | Wikipedia | 2026-03-22 | 22–23 March\: Italy \> Rovigo\, by\-election |
| partial\_unit | Wikipedia | 2026-03-22 | 22–23 March\: Italy \> Selvazzano Dentro\, by\-election |
| partial\_unit | Wikipedia | 2026-04-07 | 7 April\: United States \> Wisconsin \> Supreme Court |
| partial\_unit | Wikipedia | 2026-04-09 | 9 April\: \> New Zealand\, Ōtara\-Papatoetoe\, by\-election |
| partial\_unit | Wikipedia | 2026-05-12 | 12 May\: \> United States \> West Virginia\, Supreme Court of Appeals |
| partial\_unit | Wikipedia | 2026-05-16 | 16 May\: \> Australia\, Queensland\, Stafford by\-election |
| partial\_unit | Wikipedia | 2026-05-19 | 19 May\: United States \> Georgia \> Supreme Court |
| partial\_unit | Wikipedia | 2026-05-19 | 19 May\: United States \> Georgia \> Court of Appeals |
| partial\_unit | Wikipedia | 2026-06-02 | 2 June\: United States \> California \> Los Angeles\, Mayor \(1st round\)\, City Attorney \(1st round\)\, City Controller\, and City Council \(1st round\) |
| partial\_unit | Wikipedia | 2026-06-02 | 2 June\: United States \> California \> Los Angeles County\, Board of Supervisors\, Sheriff \(1st round\)\, and Assessor |
| partial\_unit | Wikipedia | 2026-06-14 | 14 June\: Switzerland \> Glarus\, Landrat |
| partial\_unit | Wikipedia | 2026-06-16 | 16 June\: United States \> District of Columbia\, at\-large\, special election |
| partial\_unit | Wikipedia | 2026-06-23 | 23 June\: \> Canada\, Nova Scotia\, Chéticamp\-Margarees\-Pleasant Bay\, by\-election |
| partial\_unit | Wikipedia | 2026-07-13 | 13 July\: Canada\, Prince Edward Island\, Cornwall\-Meadowbank\, by\-election |
| partial\_unit | Wikipedia | 2026-07-21 | 21 July\: \> Canada\, Manitoba\, The Pas\-Kameesak\, by\-election |
| partial\_unit | Wikipedia | 2026-08-06 | 6 August\: United States\, Tennessee \> Supreme Court\, retention elections |
| partial\_unit | Wikipedia | 2026-08-21 | 21 August\: New Zealand\, Greater Wellington\, Wairarapa\, by\-election |
| partial\_unit | Wikipedia | 2026-08-29 | 29 August\: \> Australia\, Western Australia\, Secret Harbour by\-election |
| partial\_unit | Wikipedia | 2026-08-31 | 31 August\: Canada \> Chicoutimi—Le Fjord\, by\-election |
| partial\_unit | Wikipedia | 2026-08-31 | 31 August\: Canada \> Beaches—East York\, by\-election |
| partial\_unit | Wikipedia | 2026-08-31 | 31 August\: Canada \> North Vancouver—Capilano\, by\-election |
| partial\_unit | Wikipedia | 2026-09-03 | 3 September\: Canada\, Ontario \> Scarborough Southwest\, by\-election |
| partial\_unit | Wikipedia | 2026-09-03 | 3 September\: Canada\, Ontario \> Hamilton East—Stoney Creek\, by\-election |
| partial\_unit | Wikipedia | 2026-09-03 | 3 September\: Canada\, Ontario \> York—Simcoe\, by\-election |
| partial\_unit | Wikipedia | 2026-09-12 | 12 September\: Australia\, Northern Territory\, Mulka\, by\-election |
| partial\_unit | NDI | 2026-09-14 | 2026 Philippines \(BARMM\) Parliamentary Elections \| September 14\, 2026 \(ALL DAY\) \| Parliamentary |
| partial\_unit | Wikipedia | 2026-09-14 | 14 September\: \> Canada\, Alberta\, Calgary\-Shaw\, by\-election |
| partial\_unit | Wikipedia | 2026-09-27 | 27–28 September\: Italy\, Reggio Calabria\, by\-election |
| unparsed\_unit | EISA |  | Libya \(from the row above\) \| House of Representatives \| Postponed from April 2026 |
| unparsed\_unit | Wikipedia |  | 19 May\: United States \> Oregon \> Commissioner of Labor |
| unparsed\_unit | A\-WEB |  | Ghana \| 2026 The Presidential Primaries \| 31 Jan 2026 |
| unparsed\_unit | Wikipedia |  | January\: Indonesia\, Vice President |
| unparsed\_unit | EISA |  | Libya \| Presidential \| Postponed from April 2026 |
| unparsed\_unit | Wikipedia |  | 16 July\: United Kingdom\, Norfolk\, police and crime commissioner by\-election |
| unparsed\_unit | Wikipedia |  | April and October\: India\, Rajya Sabha |
| unparsed\_unit | Wikipedia |  | 3 April\: Myanmar\, Vice President |
