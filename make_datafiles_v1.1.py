import sys
import os
import glob
import hashlib
import struct
import subprocess
import collections
import time
import tensorflow as tf
from tensorflow.core.example import example_pb2

dm_single_close_quote = u'\u2019' # unicode
dm_double_close_quote = u'\u201d'
END_TOKENS = ['.', '!', '?', '...', "'", "`", '"', dm_single_close_quote, dm_double_close_quote, ")"] # acceptable ways to end a sentence
#syntactic_tag
SYNTACTIC_TAG =['S','NP','NN','NNP','NNS','NAC','VP','PP','PRN','POS',
                 'PRP','PRP$','DT','ADVP','TO','CC','CD','IN','SBAR','SYM',
                'WHNP','WDT','VB','VBZ','VBN','VBG','VBD','VBP','JJ','JJR',
                'MD','WS','RB','QP','X']


# We use these to separate the summary sentences in the .bin datafiles
SENTENCE_START = '<s>'
SENTENCE_END = '</s>'
#
NO_IN_VOCAB = SYNTACTIC_TAG + [SENTENCE_START,SENTENCE_END]

all_train_urls = "url_lists/all_train.txt"
all_val_urls = "url_lists/all_val.txt"
all_test_urls = "url_lists/all_test.txt"
cnn_wayback_test_urls = "url_lists/cnn_wayback_test_urls.txt"

cnn_tokenized_stories_dir = "cnn_stories_tokenized"
dm_tokenized_stories_dir = "dm_stories_tokenized"
cnn_parsed_stories_dir = "cnn_stories_parsed"
dm_parsed_stories_dir = "dm_stories_parsed"
cnn_preproccessed_stories_dir = "cnn_stories_preproccessed"
dm_preproccessed_stories_dir = "dm_stories_preproccessed"
finished_files_dir = "finished_files"
chunks_dir = os.path.join(finished_files_dir, "chunked")

# These are the number of .story files we expect there to be in cnn_stories_dir and dm_stories_dir
#num_expected_cnn_stories = 92579
#num_expected_dm_stories = 219506
num_expected_cnn_stories = 2


#VOCAB_SIZE = 200000
VOCAB_SIZE = 4
CHUNK_SIZE = 1000 # num examples per chunk, for the chunked data


def chunk_file(set_name):
  in_file = 'finished_files/%s.bin' % set_name
  reader = open(in_file, "rb")
  chunk = 0
  finished = False
  while not finished:
    chunk_fname = os.path.join(chunks_dir, '%s_%03d.bin' % (set_name, chunk)) # new chunk
    with open(chunk_fname, 'wb') as writer:
      for _ in range(CHUNK_SIZE):
        len_bytes = reader.read(8)
        if not len_bytes:
          finished = True
          break
        str_len = struct.unpack('q', len_bytes)[0]
        example_str = struct.unpack('%ds' % str_len, reader.read(str_len))[0]
        writer.write(struct.pack('q', str_len))
        writer.write(struct.pack('%ds' % str_len, example_str))
      chunk += 1


def chunk_all():
  # Make a dir to hold the chunks
  if not os.path.isdir(chunks_dir):
    os.mkdir(chunks_dir)
  # Chunk the data
  for set_name in ['train', 'val', 'test']:
    print "Splitting %s data into chunks..." % set_name
    chunk_file(set_name)
  print "Saved chunked data in %s" % chunks_dir


def tokenize_stories(stories_dir, tokenized_stories_dir):
  """Maps a whole directory of .story files to a tokenized version using Stanford CoreNLP Tokenizer"""
  print "Preparing to tokenize %s to %s..." % (stories_dir, tokenized_stories_dir)
  stories = os.listdir(stories_dir)
  # make IO list file
  print "Making list of files to tokenize..."
  with open("mapping.txt", "w") as f:
    for s in stories:
      f.write("%s \t %s\n" % (os.path.join(stories_dir, s), os.path.join(tokenized_stories_dir, s)))
  command = ['java', 'edu.stanford.nlp.process.PTBTokenizer', '-ioFileList', '-preserveLines', 'mapping.txt']
  print "Tokenizing %i files in %s and saving in %s..." % (len(stories), stories_dir, tokenized_stories_dir)
  subprocess.call(command)
  print "Stanford CoreNLP Tokenizer has finished."
  os.remove("mapping.txt")

  # Check that the tokenized stories directory contains the same number of files as the original directory
  num_orig = len(os.listdir(stories_dir))
  num_tokenized = len(os.listdir(tokenized_stories_dir))
  if num_orig != num_tokenized:
    raise Exception("The tokenized stories directory %s contains %i files, but it should contain the same number as %s (which has %i files). Was there an error during tokenization?" % (tokenized_stories_dir, num_tokenized, stories_dir, num_orig))
  print "Successfully finished tokenizing %s to %s.\n" % (stories_dir, tokenized_stories_dir)

def parsing_stories(tokenized_stories_dir, parsed_stories_dir):
  """Maps a whole directory of .story files to a parsed version using BerkeleyParser-1.7"""
  print "Preparing to tokenize %s to %s..." % (tokenized_stories_dir, parsed_stories_dir)
  stories = os.listdir(tokenized_stories_dir)
  # make IO list file
  print "Making list of files to parse..."
  for s in stories:
    command = ['java', '-mx5g', '-jar', 'BerkeleyParser-1.7.jar', '-gr','eng_sm6.gr','-inputFile','./'+tokenized_stories_dir+'/'+s,'-outputFile','./'+parsed_stories_dir+'/'+s]
    subprocess.call(command)
  print "Parsing %i files in %s and saving in %s..." % (len(stories), tokenized_stories_dir, parsed_stories_dir)
  print "BerkeleyParser-1.7 has finished."

  # Check that the tokenized stories directory contains the same number of files as the original directory
  num_tokenized = len(os.listdir(tokenized_stories_dir))
  num_parsed = len(os.listdir(parsed_stories_dir))
  if num_tokenized != num_parsed:
    raise Exception("The parsed stories directory %s contains %i files, but it should contain the same number as %s (which has %i files). Was there an error during parsing?" % (parsed_stories_dir, num_parsed, tokenized_stories_dir, num_tokenized))
  print "Successfully finished parsing %s to %s.\n" % (tokenized_stories_dir, parsed_stories_dir)

def preproccess_stories(parsed_stories_dir, preproccessed_stories_dir):
  """Maps a whole directory of .story files to a parsed version using BerkeleyParser-1.7"""
  print "Preparing to tokenize %s to %s..." % (parsed_stories_dir, preproccessed_stories_dir)
  stories = os.listdir(parsed_stories_dir)
  # make IO list file
  print "Making list of files to parse..."
  for s in stories:
    f_r = open('./'+parsed_stories_dir+'/'+s, "r")
    f_w = open('./'+preproccessed_stories_dir+'/'+s,'w')
    for line in f_r.readlines():
      line = line.strip()
      if (("SYM" in line) and ("@highlight" not in line)):
        f_w.write('\n')
      else:
        line = line.replace("(","").replace(")","").strip()
        f_w.write(line+'\n')
  print "Parsing %i files in %s and saving in %s..." % (len(stories), parsed_stories_dir, preproccessed_stories_dir)
  print "BerkeleyParser-1.7 has finished."

  # Check that the tokenized stories directory contains the same number of files as the original directory
  num_parsed = len(os.listdir(parsed_stories_dir))
  num_preproccessed = len(os.listdir(preproccessed_stories_dir))
  if num_parsed != num_preproccessed:
    raise Exception("The parsed stories directory %s contains %i files, but it should contain the same number as %s (which has %i files). Was there an error during parsing?" % (preproccessed_stories_dir, num_preproccessed, parsed_stories_dir, num_parsed))
  print "Successfully finished parsing %s to %s.\n" % (parsed_stories_dir, preproccessed_stories_dir)

def read_text_file(text_file):
  lines = []
  with open(text_file, "r") as f:
    for line in f:
      lines.append(line.strip())
  return lines


def hashhex(s):
  """Returns a heximal formated SHA1 hash of the input string."""
  h = hashlib.sha1()
  h.update(s)
  return h.hexdigest()


def get_url_hashes(url_list):
  return [hashhex(url) for url in url_list]


def fix_missing_period(line):
  """Adds a period to a line that is missing a period"""
  if "@highlight" in line: return line
  if line=="": return line
  if line[-1] in END_TOKENS: return line
  # print line[-1]
  return line + " ."


def get_art_abs(story_file):
  lines = read_text_file(story_file)

  # Lowercase everything
  lines = [line.lower() for line in lines]

  # Put periods on the ends of lines that are missing them (this is a problem in the dataset because many image captions don't end in periods; consequently they end up in the body of the article as run-on sentences)
  lines = [fix_missing_period(line) for line in lines]

  # Separate out article and abstract sentences
  article_lines = []
  highlights = []
  next_is_highlight = False
  for idx,line in enumerate(lines):
    if line == "":
      continue # empty line
    elif ("@highlight" in line):
      next_is_highlight = True
    elif next_is_highlight:
      highlights.append(line)
    else:
      article_lines.append(line)

  # Make article into a single string
  article = ' '.join(article_lines)

  # Make abstract into a signle string, putting <s> and </s> tags around the sentences
  abstract = ' '.join(["%s %s %s" % (SENTENCE_START, sent, SENTENCE_END) for sent in highlights])

  return article, abstract


#def write_to_bin(url_file, out_file, makevocab=False):
def write_to_bin(glob_dir,out_file, makevocab=False):
  """Reads the tokenized .story files corresponding to the urls listed in the url_file and writes them to a out_file."""
  #print "Making bin file for URLs listed in %s..." % url_file
  # url_list = read_text_file(url_file)
  # url_hashes = get_url_hashes(url_list)
  # story_fnames = [s+".story" for s in url_hashes]
  # num_stories = len(story_fnames)


  if makevocab:
    vocab_counter = collections.Counter()

  with open(out_file, 'wb') as writer:
    # for idx,s in enumerate(story_fnames):
    #   if idx % 1000 == 0:
    #     print "Writing story %i of %i; %.2f percent done" % (idx, num_stories, float(idx)*100.0/float(num_stories))

      # Look in the preproccessed story dirs to find the .story file corresponding to this url
      #if os.path.isfile(os.path.join(cnn_preproccessed_stories_dir, s)):
        #story_file = os.path.join(cnn_preproccessed_stories_dir, s)
      # elif os.path.isfile(os.path.join(dm_preproccessed_stories_dir, s)):
      #   story_file = os.path.join(dm_preproccessed_stories_dir, s)
      #else:
        #print "Error: Couldn't find tokenized story file %s in either tokenized story directories %s and %s. Was there an error during tokenization?" % (s, cnn_preproccessed_stories_dir, dm_preproccessed_stories_dir)
        #print "Error: Couldn't find tokenized story file %s in either tokenized story directories %s. Was there an error during tokenization?" % (s, cnn_preproccessed_stories_dir)
        # Check again if tokenized stories directories contain correct number of files
        #print "Checking that the tokenized stories directories %s contain correct number of files..." % (cnn_preproccessed_stories_dir)
        #check_num_stories(cnn_preproccessed_stories_dir, num_expected_cnn_stories)
        # check_num_stories(dm_preproccessed_stories_dir, num_expected_dm_stories)
        #raise Exception("Parsed stories directories %s contain correct number of files but story file %s found in neither." % (cnn_preproccessed_stories_dir,s))

      # Get the strings to write to .bin file
      for story_file in glob.glob(glob_dir+'/*'):
        article, abstract = get_art_abs(story_file)

        # Write to tf.Example
        tf_example = example_pb2.Example()
        tf_example.features.feature['article'].bytes_list.value.extend([article])
        tf_example.features.feature['abstract'].bytes_list.value.extend([abstract])
        tf_example_str = tf_example.SerializeToString()
        str_len = len(tf_example_str)
        writer.write(struct.pack('q', str_len))
        writer.write(struct.pack('%ds' % str_len, tf_example_str))

      # Write the vocab to file, if applicable
      if makevocab:
        art_tokens = article.split(' ')
        abs_tokens = abstract.split(' ')
        abs_tokens = [t for t in abs_tokens if t not in NO_IN_VOCAB] # remove these tags from vocab
        tokens = art_tokens + abs_tokens
        tokens = [t.strip() for t in tokens] # strip
        tokens = [t for t in tokens if t!=""] # remove empty
        vocab_counter.update(tokens)

  print "Finished writing file %s\n" % out_file

  # write vocab to file
  if makevocab:
    print "Writing vocab file..."
    with open(os.path.join(finished_files_dir, "vocab"), 'w') as writer:
      for word, count in vocab_counter.most_common(VOCAB_SIZE):
        writer.write(word + ' ' + str(count) + '\n')
    print "Finished writing vocab file"


def check_num_stories(stories_dir, num_expected):
  num_stories = len(os.listdir(stories_dir))
  if num_stories != num_expected:
    raise Exception("stories directory %s contains %i files but should contain %i" % (stories_dir, num_stories, num_expected))


if __name__ == '__main__':
  start = time.clock()
  print('start time: %s Seconds'%(start))
  # cnn_stories_dir = "./cnn/stories"
  # check_num_stories(cnn_stories_dir, num_expected_cnn_stories)

  # if not os.path.exists(cnn_tokenized_stories_dir): os.makedirs(cnn_tokenized_stories_dir)
  # if not os.path.exists(cnn_parsed_stories_dir): os.makedirs(cnn_parsed_stories_dir)
  # if not os.path.exists(cnn_preproccessed_stories_dir): os.makedirs(cnn_preproccessed_stories_dir)
  # if not os.path.exists(finished_files_dir): os.makedirs(finished_files_dir)
  
  # tokenize_stories(cnn_stories_dir, cnn_tokenized_stories_dir)

  # parsing_stories(cnn_tokenized_stories_dir, cnn_parsed_stories_dir)

  #preproccess_stories(cnn_parsed_stories_dir, cnn_preproccessed_stories_dir)

  write_to_bin(cnn_preproccessed_stories_dir, os.path.join(finished_files_dir, "cnn_wayback_test.bin"))
  write_to_bin(cnn_preproccessed_stories_dir, os.path.join(finished_files_dir, "cnn_wayback_train.bin"),makevocab=True)
  #chunk_all()

  end = time.clock()
  print('end time: %s Seconds'%(end))
  print('Running time: %s Seconds'%(end-start)) #end-start is the time the program is running, in seconds.